"""Previsao linear experimental de proximidade em dois eixos; somente offline."""
from collections import deque
from detect_proximity import Detector

def interval(position, velocity, radius, horizon):
    if velocity == 0:
        return (0.0, float(horizon)) if abs(position) <= radius else None
    a,b=sorted(((-radius-position)/velocity,(radius-position)/velocity))
    lo,hi=max(0.0,a),min(float(horizon),b)
    return (lo,hi) if lo<=hi else None

class PredictiveDetector(Detector):
    # Janela de 3 frames para reduzir a alternancia de registros atualizados
    # em frames diferentes. Sem informacao futura ou estado entre resets.
    def __init__(self, limits=None):
        if limits is None:super().__init__()
        else:super().__init__(limits)
        self.history=deque(maxlen=4)

    def update(self,player,racers):
        result=super().update(player,racers)
        self.history.append((player['frame'],dict(self.previous)))
        for row in result:
            row.update(prediction_valid=0,longitudinal_velocity=None,lateral_velocity=None,
                       predicted_entry_frames=None,predicted_warning=0)
            if len(self.history)<4:continue
            samples=[h[1][row['id']] for h in self.history]
            # Rejeita wrap ambiguo/salto; lateral bruta nao e coordenada circular.
            if any(a[2]!=b[2] or abs(b[0]-a[0])>self.limits.max_relative_delta
                   or abs(b[1]-a[1])>4096 for a,b in zip(samples,samples[1:])):continue
            dt=self.history[-1][0]-self.history[0][0]
            vg=(samples[-1][0]-samples[0][0])/dt
            vl=(samples[-1][1]-samples[0][1])/dt
            x=interval(row['gap'],vg,self.limits.longitudinal_warning,self.limits.horizon_frames)
            y=interval(row['lateral_delta'],vl,self.limits.lateral_warning,self.limits.horizon_frames)
            entry=max(x[0],y[0]) if x and y and max(x[0],y[0])<=min(x[1],y[1]) else None
            row.update(prediction_valid=1,longitudinal_velocity=vg,lateral_velocity=vl,
                       predicted_entry_frames=entry,predicted_warning=int(entry is not None))
        return result
