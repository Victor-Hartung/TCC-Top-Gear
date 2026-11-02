"""Teste causal curto com o BizHawk real. Nao treina e nao usa modelo."""
from __future__ import annotations
from dataclasses import asdict
import time
from experiment import atomic_json, contract, contract_hash, source_hashes, unique_name, environment_versions, critical_sources, preflight_receipt_path
from protocol import BridgeClient
from telemetry import Telemetry, ObservationBuilder, OBSERVATION_NAMES, observation_names
from topgear_config import ProjectConfig
from terminal_progress import write_progress, clear_progress
from live_detector import VERSION as DETECTOR_VERSION
from native_navigation import SETTINGS as NAVIGATION_SETTINGS


def record_observation(record, observations, state):
    observation = observations.build(state)
    record['detector_features'] = observation[26:47].tolist()
    record['navigation_features'] = observation[47:61].tolist()
    record['observation'] = observation.tolist()
    record['detector_candidates'] = observations.detector_rows
    record['navigation'] = observations.navigation


def prepare_controls(bridge, cfg, start, states):
    """Prefixo causal apenas do teste; treino nunca usa aceleracao automatica.

    lap=0 e velocidade minima estabelecem uma base comparavel, nao detectam GO.
    Todas as transicoes ficam no relatorio, inclusive em caso de falha.
    """
    if start.lap >= 0:
        return start
    state = start
    limit = cfg.integer('episode', 'prestart_max_steps')
    observations = ObservationBuilder(cfg)
    observations.reset(start)
    for i in range(limit):
        previous = state
        state = Telemetry.from_fields(bridge.step(1).fields)
        states.append(asdict(state))
        state.assert_runtime_ready(allow_prestart=True, require_detector=True)
        if len(state.detector_samples.split(';')) != 4:
            raise ValueError('Detector precisa de quatro frames em cada step')
        record_observation(states[-1], observations, state)
        if previous.lap >= 0 and state.lap < 0:
            raise ValueError("Volta regrediu ao sentinela durante a largada")
        if state.track_length != 22528 or state.total_laps != 3 or state.lap > 0:
            raise ValueError('Perfil/volta mudou durante a largada')
        if state.race_ended:
            raise ValueError('Corrida terminou na largada; confira o save e o relatorio')
        if state.collision_events < previous.collision_events:
            raise ValueError('Contador de impactos regrediu durante a largada')
        write_progress(f'Largada: {i+1}/{limit} passos (limite), lap={state.lap}, speed={state.speed}')
        if (state.lap == 0 and state.speed >= 1500 and not state.collision
                and state.collision_events == previous.collision_events):
            clear_progress()
            return state
    raise ValueError('Largada nao atingiu lap=0, speed>=1500 e janela sem novo impacto dentro do limite; investigar o JSON')


def check_manual_controls(bridge, cfg, report):
    """Teste de transporte/controles. Nao procura ponto ideal de troca."""
    states = report['manual_control_states'] = []
    start = Telemetry.from_fields(bridge.reset().fields)
    launch = report['manual_launch_states'] = []
    start = prepare_controls(bridge, cfg, start, launch)
    observations = ObservationBuilder(cfg)
    observations.reset(start)
    if start.gear != 0:
        raise ValueError('Preflight manual exige save 2 na largada, primeira marcha')
    def step(action, gear):
        from manual_transmission import decode_action
        wire = bridge.step(action)
        state = Telemetry.from_fields(wire.fields)
        record = {'action': action, 'expected_gear': gear, **asdict(state)}
        states.append(record)
        state.assert_runtime_ready(allow_prestart=True, require_detector=True)
        obs = observations.build(state, shift_command=decode_action(action)[1])
        record['observation'] = obs.tolist()
        if state.gear != gear:
            raise ValueError(f'Troca manual: esperado {gear}, recebido {state.gear}; veja manual_control_states')
        if state.race_ended or state.offtrack or state.collision_events > start.collision_events:
            raise ValueError('Impacto/saida/termino durante teste de comandos manuais')
        return state
    for gear in range(1, 5):
        step(1, gear-1)  # quatro frames de liberacao real do botao R
        step(11, gear)   # X+R
        step(11, gear)   # R mantido nao deve gerar outra troca
    step(1, 4)
    step(11, 4)         # limite da quinta
    for gear in range(3, -1, -1):
        step(1, gear+1)
        step(21, gear)   # X+L
        step(21, gear)
    step(1, 0)
    step(21, 0)         # limite da primeira
    report['checks']['manual_R_L_release_and_limits'] = True
    report['checks']['manual_gauge_present_and_varies'] = len({s['engine_gauge_raw'] for s in states}) > 1
    report['checks']['manual_63_features'] = all(len(s['observation']) == 63 for s in states)


def main() -> None:
    cfg = ProjectConfig.load()
    expected = contract(cfg)
    directory = cfg.project_dir / 'runs' / 'preflight'
    report = {'version': 2, 'status': 'running', 'execution': 'live_bizhawk',
              'contract_sha256': contract_hash(expected), 'source_hashes': source_hashes(cfg.project_dir),
              'critical_sources': critical_sources(cfg.project_dir),
              'environment': environment_versions(), 'observation_names': list(observation_names(cfg)),
              'detector_integration': DETECTOR_VERSION, 'navigation_settings': NAVIGATION_SETTINGS,
              'checks': {}, 'branches': {}}
    path = directory / (unique_name('preflight') + '.json')
    bridge = None
    try:
        bridge = BridgeClient(cfg)
        script = ('Top Gear Manual (USA).lua' if cfg.manual_transmission else
                  'Top Gear Azul Automatico (USA).lua' if cfg.blue_auto_expected else
                  'Top Gear (USA).lua')
        print(f'Servidor em {bridge.address}. Abra o BizHawk e somente lua/{script}.', flush=True)
        ready = bridge.wait_ready()
        report['hello'] = ready.fields
        starts = []
        for name, action in [('coast', 0), ('accelerate', 1), ('brake', 2), ('left', 3), ('right', 4)]:
            reset_fields = bridge.reset().fields
            if cfg.blue_auto_expected:
                from blue_auto import validate_wire
                validate_wire(reset_fields)
                report.setdefault('blue_auto_reset_identity', []).append({
                    key: reset_fields[key] for key in
                    ('manual_mode', 'car_table_offset_raw', 'upshift_mask_raw', 'downshift_mask_raw')
                })
            start = Telemetry.from_fields(reset_fields)
            start.assert_runtime_ready(allow_prestart=True, require_detector=True)
            if start.race_ended or start.track_length != 22528 or start.total_laps != 3:
                raise ValueError('Savestate deve estar em Las Vegas, corrida ativa, tres voltas')
            if len(start.detector_samples.split(';')) != 1:
                raise ValueError('Reset deve limpar historico do detector')
            starts.append(asdict(start))
            launch = []
            report['branches'][name] = {'initial': asdict(start), 'launch_states': launch, 'states': []}
            initial_builder = ObservationBuilder(cfg)
            record_observation(report['branches'][name]['initial'], initial_builder, start)
            start = prepare_controls(bridge, cfg, start, launch)
            if start.curve_current != 0 or start.offtrack:
                raise ValueError('Para este teste causal use um save na contagem regressiva da reta inicial, no asfalto')
            observations = ObservationBuilder(cfg)
            observations.reset(start)
            states = []
            report['branches'][name].update({'control_initial': asdict(start), 'states': states})
            for i in range(12):
                if i == 0:
                    time.sleep(0.05)
                wire = bridge.step(action).fields
                report['last_wire_state'] = dict(wire)
                state = Telemetry.from_fields(wire)
                states.append(asdict(state))
                state.assert_runtime_ready(require_detector=True)
                if len(state.detector_samples.split(';')) != 4:
                    raise ValueError('Detector precisa de quatro frames em cada step')
                record_observation(states[-1], observations, state)
                if state.collision_events < start.collision_events:
                    raise ValueError('Contador de impactos regrediu durante o ramo')
                if state.race_ended or state.collision or state.collision_events > start.collision_events:
                    raise ValueError('Ramo teve impacto/termino: salve mais cedo na reta e repita')
            report['branches'][name].update({'control_initial': asdict(start), 'states': states})
            print(f'{name}: speed {start.speed}->{state.speed}, lateral {start.lateral}->{state.lateral}', flush=True)
        checks = report['checks']
        checks['identical_reset_telemetry'] = all(s == starts[0] for s in starts)
        endings = {name: row['states'][-1] for name, row in report['branches'].items()}
        launches = [row['launch_states'] for row in report['branches'].values()]
        report['launch_collision_events'] = {name: row['control_initial']['collision_events'] - row['initial']['collision_events']
                                             for name, row in report['branches'].items()}
        checks['identical_launch_replay'] = all(row == launches[0] for row in launches)
        checks['accelerate_beats_coast'] = endings['accelerate']['speed'] > endings['coast']['speed']
        checks['brake_not_faster_than_coast'] = endings['brake']['speed'] <= endings['coast']['speed']
        checks['steering_orders_lateral'] = endings['left']['lateral'] < endings['accelerate']['lateral'] < endings['right']['lateral']
        checks['fixed_frames_and_observation_bounds'] = True
        checks['observation_61_features_and_per_frame_history'] = len(OBSERVATION_NAMES) == 61
        checks['detector_prediction_seen'] = any(r['prediction_valid'] for b in report['branches'].values() for s in b['states'] for r in s['detector_candidates'])
        # Conferencia das mascaras em cada frame, nao somente no ultimo frame
        # de uma decisao. Recibo antigo nao libera esta extensao de memoria.
        from live_detector import parse_samples
        from native_navigation import augment_samples
        samples = []
        for branch in report['branches'].values():
            for record in [branch['initial'], *branch['launch_states'], *branch['states']]:
                state = Telemetry.from_fields({k: str(v) for k, v in record.items()})
                _, parsed = augment_samples(state.navigation_samples, parse_samples(state.detector_samples, state))
                samples.extend(parsed)
        report['navigation_frames_checked'] = len(samples)
        # Chaves preenchidas pelo decodificador; detalhes brutos ficam no JSON.
        checks['navigation_identity_and_corridor_every_frame'] = bool(samples) and all(s['identity_valid'] and s['corridor_valid'] for s in samples)
        checks['p2_prediction_seen'] = any(r['id'] == 1 and r['prediction_valid'] for b in report['branches'].values() for s in [*b['launch_states'], *b['states']] for r in s['detector_candidates'])
        if cfg.blue_auto_expected:
            checks['blue_car_and_auto_masks_on_five_resets'] = len(report['blue_auto_reset_identity']) == 5
        if cfg.manual_transmission:
            check_manual_controls(bridge, cfg, report)
        if not all(checks.values()):
            raise ValueError(f'Preflight reprovado: {checks}')
        report['reset_fingerprint'] = starts[0]
        report['status'] = 'passed'
    except BaseException as exc:
        report['status'] = 'failed'
        report['error'] = repr(exc)
        raise
    finally:
        clear_progress()
        if bridge is not None:
            bridge.close()
        atomic_json(path, report)
        # Uma tentativa nova reprovada invalida a aprovacao anterior; historicos
        # individuais continuam preservados com seus nomes unicos.
        atomic_json(preflight_receipt_path(cfg), report)
        print(f'RELATORIO: {path.resolve()}', flush=True)
        if report['status'] == 'passed':
            print('PREFLIGHT OK. Comunicacao/reset/controles e leitura P2/corredor; isto nao demonstra aprendizado nem ausencia de colisoes.')


if __name__ == '__main__':
    import argparse
    argparse.ArgumentParser(description=__doc__).parse_args()
    main()
