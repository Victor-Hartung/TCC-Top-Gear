"""Detector integrado experimental: pacote de ate4frames; sem controle automatico."""
from protocol import ProtocolError

VERSION=3
SETTINGS=dict(version=VERSION,history_frames=4,sensor_fraction=0.1,alongside_gap=32,
              longitudinal_warning=100,lateral_warning=4096,horizon_frames=30,
              max_relative_delta=100,max_lateral_delta=4096,
              selection="highest_risk_then_nearest_then_id",p2_identity="dynamic_record_offset")
REGIONS=('front','rear','alongside')
FEATURE_NAMES=tuple('detector_'+region+'_'+key for region in REGIONS for key in
                    ('present','gap','lateral','long_velocity','lateral_velocity','prediction_valid','risk'))
LOW=[v for _ in REGIONS for v in (0,-1,-1,-1,-1,0,0)]

def interval(p,v,r,h):
    if v==0:return (0.,float(h)) if abs(p)<=r else None
    a,b=sorted(((-r-p)/v,(r-p)/v));lo,hi=max(0.,a),min(float(h),b)
    return (lo,hi) if lo<=hi else None

def parse_samples(text, telemetry):
    if not text or len(text)>16000:raise ProtocolError('Detector sem historico ou pacote excessivo')
    result=[]
    try:
        for sample in text.split(';'):
            vals=[int(s) for s in sample.split(',')]
            if len(vals)!=58:raise ValueError('tamanho de amostra')
            f,p,l,length=vals[:4]
            if f<0 or length!=22528 or not 0<=p<length or not -32768<=l<=32767:raise ValueError('jogador')
            racers={}
            for i in range(4,len(vals),3):
                identity,progress,lateral=vals[i:i+3]
                if identity not in range(2,20) or identity in racers or not 0<=progress<length or not -32768<=lateral<=32767:raise ValueError('registro adversario')
                racers[identity]=(progress,lateral)
            result.append((f,p,l,length,racers))
        if len(result) not in (1,4):raise ValueError('historico deve ter1 ou4frames')
        if any(b[0]!=a[0]+1 for a,b in zip(result,result[1:])):raise ValueError('frames nao consecutivos')
        if result[-1][:4]!=(telemetry.frame,telemetry.progress,telemetry.lateral,telemetry.track_length):raise ValueError('pacote nao corresponde ao estado')
    except (ValueError,TypeError) as exc:raise ProtocolError('Historico do detector invalido: '+str(exc)) from exc
    return result

def evaluate(text,telemetry):
    samples=parse_samples(text,telemetry)
    navigation_text=getattr(telemetry,'navigation_samples','')
    if navigation_text:
        from native_navigation import augment_samples
        samples,_=augment_samples(navigation_text,samples)
    return evaluate_samples(samples)


def evaluate_samples(samples):
    """IDs 2..19 originais; ID 1 reservado a P2 identificado pelo offset.

    Um registro P2 inconsistente perde a previsao, nunca herda a velocidade
    de outro carro quando a tabela muda de ordem.
    """
    last=samples[-1];rows=[]
    for identity in sorted(last[4]):
        trajectory=[]
        for _,p,l,length,racers in samples:
            if identity not in racers:
                continue
            other,lat=racers[identity]
            trajectory.append(((other-p+length//2)%length-length//2,lat-l))
        gap,lateral=trajectory[-1]
        if abs(gap)>last[3]*SETTINGS['sensor_fraction']:continue
        valid=len(trajectory)==len(samples)==4 and all(abs(b[0]-a[0])<=100 and abs(b[1]-a[1])<=4096 for a,b in zip(trajectory,trajectory[1:]))
        vg=(gap-trajectory[0][0])/3 if valid else 0.
        vl=(lateral-trajectory[0][1])/3 if valid else 0.
        x=interval(gap,vg,100,30) if valid else None;y=interval(lateral,vl,4096,30) if valid else None
        entry=max(x[0],y[0]) if x and y and max(x[0],y[0])<=min(x[1],y[1]) else None
        region='alongside' if abs(gap)<=32 else 'front' if gap>0 else 'rear'
        rows.append(dict(id=identity,gap=gap,lateral_delta=lateral,region=region,
                         prediction_valid=int(valid),long_velocity=vg,lateral_velocity=vl,
                         predicted_entry_frames=entry,predicted_warning=int(entry is not None),
                         risk=max(0.,1.-entry/30.) if entry is not None else 0.))
    rows.sort(key=lambda r:(abs(r['gap']),r['id']))
    for row in rows:row['selected_for_observation']=False
    features=[]
    clip=lambda v:max(-1.,min(1.,v))
    for region in REGIONS:
        group=[r for r in rows if r['region']==region]
        if not group:features.extend([0.]*7);continue
        # Todos os campos do grupo devem descrever o mesmo carro. Misturar
        # lateral do mais proximo com risco de outro carro ensina associacao falsa.
        nearest=min(group,key=lambda r:(-r['risk'],abs(r['gap']),r['id']))
        nearest['selected_for_observation']=True
        features.extend([1.,clip(nearest['gap']/(last[3]*.1)),clip(nearest['lateral_delta']/65536.),
                         clip(nearest['long_velocity']/100.),clip(nearest['lateral_velocity']/4096.),
                         float(nearest['prediction_valid']),nearest['risk']])
    return features,rows
