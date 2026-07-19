# Processo Seletivo – Intensivo Maker | IoT
## Relatório do Candidato: Sistema de Monitoramento Termal e Acesso

### Identificação do Candidato
**Nome completo:** Carlos André Alves Torres Filho
**GitHub:** carlos-andre-alves

### Visão Geral da Solução
O projeto consiste em um sistema embarcado desenvolvido para atuar como um dispositivo de auditoria de qualidade em ambientes sensíveis (como estufas ou coolers industriais). A solução monitora, simultaneamente, o tempo de exposição prolongada causado pela abertura da porta e a elevação indesejada do gradiente térmico ($\Delta T$). O sistema interage com o usuário/operador através do envio de logs seriais e alertas em tempo real.

### Arquitetura do Sistema Embarcado
A arquitetura foi desenhada no modelo de **Máquina de Estados Não-Bloqueante**.
* **Fluxo Principal (`main.py`):** O loop não possui instruções de atraso longo (`sleep`). O tempo é gerenciado pela diferença milissegundo a milissegundo através da função nativa `time.ticks_ms()`.
* **Concorrência:** O firmware avalia as duas falhas (porta e temperatura) de forma concorrente. Caso ambos os eventos de falha ocorram, o código só retorna ao estado natural se **ambas** as premissas (porta fechada E delta T restabelecido) forem solucionadas em conjunto.
* **Comunicação I2C Raw:** Para o monitoramento térmico, optou-se pela comunicação via barramento `SoftI2C` com leituras diretas aos registradores do sensor, removendo as camadas de abstração.

### Componentes Utilizados na Simulação
1. **ESP32 DevKit C:** Placa de desenvolvimento microcontroladora responsável pela lógica e processamento serial.
2. **MPU6050 (ID: `imu1`):** Acelerômetro e Giroscópio com sensor térmico embutido. Utilizado para extrair a temperatura real do ambiente via leitura dos registradores `0x41` e `0x42`.
3. **Botão Físico (ID: `btn1`):** Mapeado na porta GPIO4 utilizando uma lógica interna de *Pull-Down*. Atua como o fim-de-curso da porta, onde Nível Alto (`1`) reflete a porta fechada e Nível Baixo (`0`) reflete a porta aberta.

### Decisões Técnicas Relevantes
* **Clean Code e Abstração de Hardware:** Em vez de utilizar números espalhados no código, foram definidas constantes de configuração (`LIMITE_TEMPO_PORTA_MS`, `LIMITE_VARIACAO_TEMP_C`) no topo do arquivo. 
* **Ausência de Bibliotecas Externas:** O maior gargalo de automações de testes (CI/CD) são dependências falhas. Para garantir a confiabilidade da esteira do Wokwi, o código realiza as chamadas *raw* via I2C para o MPU6050. Isso evidencia domínio do protocolo sem a muleta de *libs* fechadas.
* **Edge Detection:** Os alarmes enviam a mensagem via Serial apenas uma vez durante a ocorrência do evento (usando as variáveis `alarme_porta_ativo` e `alarme_temp_ativo`), impedindo o *flood* de mensagens na porta serial.

### Resultados Obtidos
O sistema obedece a todas as especificações dinâmicas impostas pelas restrições do cenário:
1. Detecta aberturas e estouros de *timers* parametrizados.
2. Identifica gradientes térmicos acima de $3^\circ\text{C}$ da linha-base estável.
3. Garante que os alertas se cessem estritamente quando o sistema retorna à zona de conforto térmico e físico de forma simultânea.
O código passa no *pipeline* de testes automatizados com sucesso, sem *warnings* e em total sincronia de *strings* seriais.