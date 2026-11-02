# Histórico preservado

Estes modelos, logs, fontes e diagnósticos pertencem às versões anteriores. Não alimentam automaticamente o treino v3. Arquivos originais de evidência foram copiados sem alteração de bytes. Pacotes históricos em `source` permitem recuperar v2.0.28, correção de término e road_v1; não os extraia por cima da v3.

`models/final_10240_steps.zip` é um modelo antigo sem contrato v3. A recusa de carregamento é intencional: observações/escala/ação/reward mudaram. Avaliações anteriores já estão preservadas em `evidence`. Os modelos não foram convertidos nem regravados.

O inventário externo completo está em `docs/INVENTORY.json`. Referências a árvores de auditoria nesse inventário são proveniência; não são dependências de execução e nem todos os anexos gigantes de emulador/venv são duplicados neste ZIP.

Documentos em `docs/history` têm valor histórico. Afirmações antigas como finished=chegada, índice/16 de curva ou capacidade zero de adversários referem-se às versões então existentes e foram corrigidas no relatório atual.
