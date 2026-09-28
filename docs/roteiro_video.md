# Roteiro de vídeo (até 5 minutos, narração humana)

**0:00–0:35 — Problema.** Explicar prevenção de riscos em frotas e o uso exclusivo de dados fictícios nesta demonstração.

**0:35–1:30 — Entrada.** Mostrar `data/raw/sample_events.json`, executar `python -m app.ingestion --input data/raw/sample_events.json`, repetir para demonstrar idempotência e mostrar o registro rejeitado em um teste.

**1:30–2:35 — Saída.** Abrir o dashboard local; mostrar score, prioridade, fatores, filtros por região e operação, tendência e comparativos. Mencionar que o score exibido é experimental.

**2:35–3:25 — Arquitetura.** Mostrar o diagrama no README e explicar banco, validação, features, modelo e API.

**3:25–4:20 — Modelo e segurança.** Mostrar `models/risk_model.json`, explicar que métricas são reais da base **sintética**, e demonstrar 401/403 com tokens e a verificação do log.

**4:20–5:00 — Testes e limites.** Executar `python -m pytest -q`, falar das limitações e próximos passos. Publicar vídeo no YouTube como não listado e adicionar o link ao README.
