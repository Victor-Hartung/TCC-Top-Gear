"""Raw ROM-derived candidates, isolated from training. Live semantics pending."""
from protocol import BridgeClient, ProtocolError


FIELDS = (
    'frame', 'finishers', 'active_mask', 'physics_phase', 'control_word',
    'p1_auto_byte', 'p1_flags', 'transition_countdown', 'message_pending',
    'message_id', 'message_ticks', 'lap', 'final_rank', 'rank', 'speed',
    'fuel', 'progress', 'total_laps', 'clock_candidate', 'p1_finish_time_candidate',
) + tuple(f'finish_order_{i}' for i in range(20))


class NativeFinishBridge(BridgeClient):
    def _command_text(self, **kwargs):
        text = super()._command_text(**kwargs)
        return text + ('|finish_probe=1' if kwargs['kind'] == 'hello' else '')

    def wait_ready(self, timeout=None):
        state = super().wait_ready(timeout)
        if state.fields.get('finish_probe') != '1':
            raise ProtocolError('Abra somente lua/diagnostico_fim_corrida.lua para este teste')
        return state


def parse_samples(fields, previous_frame=None):
    if fields.get('finish_probe') != '1':
        raise ProtocolError('Amostras nativas ausentes; use diagnostico_fim_corrida.lua')
    text = fields.get('finish_samples', '')
    try:
        rows = [list(map(int, record.split(','))) for record in text.split(';')]
        if any(len(row) != len(FIELDS) for row in rows):
            raise ValueError('numero de campos')
        samples = [dict(zip(FIELDS, row)) for row in rows]
        current_frame = int(fields['frame'])
        expected = [current_frame] if previous_frame is None else list(range(previous_frame+1, current_frame+1))
        if not 1 <= len(expected) <= 4 or [s['frame'] for s in samples] != expected:
            raise ValueError('frames ausentes, duplicados ou fora de ordem')
        signed = {'physics_phase', 'message_id', 'lap', 'final_rank', 'speed'}
        byte = {'p1_auto_byte', 'p1_flags'} | {f'finish_order_{i}' for i in range(20)}
        for sample in samples:
            for key, value in sample.items():
                low, high = ((0, 2**53) if key == 'frame' else
                             (-32768, 32767) if key in signed else
                             (0, 255) if key in byte else (0, 65535))
                if not low <= value <= high:
                    raise ValueError(f'{key} fora da largura de memoria')
        # Last sample and ordinary telemetry are read without advancing a frame.
        for key in ('lap', 'final_rank', 'rank', 'speed', 'fuel', 'progress', 'total_laps'):
            if samples[-1][key] != int(fields[key]):
                raise ValueError(f'{key} difere da telemetria do mesmo frame')
        return samples
    except (KeyError, ValueError) as exc:
        raise ProtocolError(f'Captura nativa inconsistente: {exc}') from exc


def summarize(samples):
    """Describe observed crossings; never promote these into successful episodes."""
    predicates = {
        'first_result': lambda s: 0 <= s['final_rank'] <= 19,
        'first_ten_finishers': lambda s: 10 <= s['finishers'] <= 20,
        'first_lap_three': lambda s: s['lap'] == s['total_laps'] == 3,
        'first_p1_in_finish_order': lambda s: 1 <= s['finishers'] <= 20 and
            0 in [s[f'finish_order_{i}'] for i in range(s['finishers'])],
        'first_message_35': lambda s: s['message_id'] == 35,
    }
    result = {name: next((s for s in samples if predicate(s)), None)
              for name, predicate in predicates.items()}
    result['note'] = ('Raw observations only. A crossing after the native cutoff does not '
                      'prove successful completion. HUD clock units are not validated.')
    return result
