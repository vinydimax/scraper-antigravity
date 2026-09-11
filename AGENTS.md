# Diretrizes Operacionais do Projeto (Antigravity)

## Stack Técnica
- Linguagem: Python 3.11+
- Testes: Pytest
- Scraping/HTTP: HTTPX e BeautifulSoup4
- Tipagem: Tipos explícitos (Type Hinting)

## Regras de Execução Agentiva
1. Sempre crie testes unitários para novas funções antes ou em conjunto com a implementação.
2. Toda alteração de código deve ser validada executando pytest no shell.
3. Se um teste falhar, analise o erro e aplique o self-healing sem pedir confirmação para mudanças triviais.
4. Nunca versione senhas, chaves de API ou segredos.
