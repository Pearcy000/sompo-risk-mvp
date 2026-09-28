def explain(event):
    factors = []
    if event.get("engine_temp_c") is None:
        factors.append("Temperatura ausente: verificar sensor")
    elif event["engine_temp_c"] >= 100:
        factors.append("Temperatura elevada: verificar arrefecimento")
    if event["maintenance_days"] >= 20:
        factors.append("Manutenção atrasada: agendar revisão")
    if event.get("hard_brakes", 0) >= 5:
        factors.append("Frenagens bruscas: orientar operação")
    if event["speed_kmh"] >= 90:
        factors.append("Velocidade elevada: revisar condução")
    if (event.get("rain_mm") or 0) >= 10:
        factors.append("Chuva intensa: reduzir exposição")
    return factors[:3] or ["Sem fator dominante pelas regras demonstrativas"]


def classify(score):
    if score >= 70:
        return "alta", "Inspecionar equipamento e registrar decisão antes do próximo ciclo."
    if score >= 40:
        return "atencao", "Agendar inspeção no próximo ciclo."
    return "normal", "Manter acompanhamento da operação."
