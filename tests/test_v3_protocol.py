from __future__ import annotations
import socket
import threading
import time
import unittest
from unittest.mock import patch
from test_protocol import socket_test_config, send_state
from protocol import BridgeClient, BridgeTimeout, ProtocolError, encode_frame, recv_frame, parse_message, ACTION_PREFIX, MAX_MESSAGE_BYTES
from protocol import BridgeState


class ProtocolFailureTests(unittest.TestCase):
    def test_manual_savestate_load_between_actions_breaks_session(self):
        client=BridgeClient(socket_test_config())
        client._last_state=BridgeState({'episode':'0','frame':'100','load_events':'1'})
        after=BridgeState({'episode':'0','frame':'104','load_events':'2'})
        try:
            with patch.object(client,'_send',return_value=(1,after)):
                with self.assertRaisesRegex(ProtocolError,'fora do comando reset'):client.step(1)
            self.assertTrue(client._broken)
        finally:client.close()

    def frame_with(self, payload):
        a,b=socket.socketpair()
        try:
            a.sendall(payload); a.shutdown(socket.SHUT_WR)
            return recv_frame(b)
        finally: a.close(); b.close()

    def test_invalid_size_empty_and_oversize(self):
        for payload in (b' 1',b'-1 a',b'0 ',str(MAX_MESSAGE_BYTES+1).encode()+b' '):
            with self.subTest(payload=payload),self.assertRaises(ProtocolError): self.frame_with(payload)

    def test_disconnect_inside_message(self):
        with self.assertRaisesRegex(ProtocolError,'fim da mensagem'): self.frame_with(b'10 abc')

    def test_invalid_utf8(self):
        with self.assertRaises(UnicodeError): self.frame_with(b'1 \xff')

    def test_total_deadline_prevents_indefinitely_partial_messages(self):
        a,b=socket.socketpair()
        try:
            a.sendall(b'10 abc')
            with patch('protocol.time.monotonic',side_effect=[.1,.2,.3,.6]):
                with self.assertRaises(TimeoutError): recv_frame(b,deadline=.5)
        finally:a.close();b.close()

    def test_coalesced_messages_are_separate(self):
        a,b=socket.socketpair()
        try:
            a.sendall(encode_frame('hello')+encode_frame('second'))
            self.assertEqual(recv_frame(b),'hello');self.assertEqual(recv_frame(b),'second')
        finally:a.close();b.close()

    def test_control_characters_and_empty_tokens(self):
        for message in ('TGACT2|a=1\n','TGACT2||a=1','TGACT2|a=1|','TGACT2|a=\x00'):
            with self.assertRaises(ProtocolError):parse_message(message,ACTION_PREFIX)

    def run_bad_peer(self, mismatch):
        cfg=socket_test_config()
        client=BridgeClient(cfg)
        errors=[]
        def peer():
            try:
                with socket.create_connection(client.address,timeout=1) as c:
                    hello=parse_message(recv_frame(c),ACTION_PREFIX)
                    send_state(c,status='ready',episode=0,ack=hello['seq'],frame=100,reset_ok=0)
                    step=parse_message(recv_frame(c),ACTION_PREFIX)
                    response={'status':'ok','episode':step['episode'],'ack':step['seq'],'frame':104,'reset_ok':0}
                    if mismatch=='ack':response['ack']=int(step['seq'])-1
                    elif mismatch=='episode':response['episode']=99
                    elif mismatch=='delta':response['frame']=105
                    elif mismatch=='lua_error':response.update(status='error',error='bad_surface')
                    elif mismatch=='timeout':return
                    send_state(c,**response)
            except Exception as e: errors.append(repr(e))
        thread=threading.Thread(target=peer,daemon=True);thread.start()
        try:
            client.wait_ready()
            with self.assertRaises(ProtocolError):client.step(0)
            with self.assertRaises(ProtocolError):client.step(0)
        finally:client.close();thread.join(1)
        self.assertEqual(errors,[])

    def test_bad_acks_episode_delta_and_lua_error_break_the_session(self):
        for kind in ('ack','episode','delta','lua_error','timeout'):
            with self.subTest(kind=kind):self.run_bad_peer(kind)

    def test_receive_timeout_and_no_replay(self):
        cfg=socket_test_config();client=BridgeClient(cfg)
        a,b=socket.socketpair()
        client._connection=b
        try:
            with self.assertRaises(BridgeTimeout):client._receive_state(.02)
        finally:a.close();client.close()

    def test_wrong_lua_revision_profile_hash_and_rom(self):
        for extra in ({'bridge_revision':2},{'profile_crc':0},{'rom_hash':'0'*40},{'domain_size':8192}):
            client=BridgeClient(socket_test_config())
            def peer():
                with socket.create_connection(client.address,timeout=1) as c:
                    hello=parse_message(recv_frame(c),ACTION_PREFIX)
                    send_state(c,status='ready',episode=0,ack=hello['seq'],frame=100,**extra)
            thread=threading.Thread(target=peer,daemon=True);thread.start()
            try:
                with self.assertRaises(ProtocolError):client.wait_ready()
            finally:client.close();thread.join(1)


if __name__=='__main__':unittest.main()
