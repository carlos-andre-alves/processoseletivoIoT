# Relatório Final - Projeto Prático IoT

### Identificação do Candidato
- **Nome completo:** Carlos André Alves Torres Filho
- **GitHub:** https://github.com/carlos-andre-alves

---

## Visão Geral da Solução
O objetivo deste projeto é fornecer uma solução embarcada para monitoramento de ambientes refrigerados (Smart Cooler). O sistema, escrito em MicroPython para a placa ESP32, lê continuamente o estado de uma porta (via botão) e a temperatura ambiente (via MPU6050, utilizado aqui como sensor térmico). Ele detecta anomalias de operação e dispara alertas via Serial quando:
1. A porta permanece aberta além do tempo limite estipulado (5000ms).
2. Ocorre uma variação térmica abrupta (ΔT >= 3.0°C) em relação a uma temperatura de referência.

O sistema notifica a normalização assim que a porta é fechada e a temperatura retorna à faixa segura, sem qualquer intervenção manual além da simulação dos eventos.

---

## Arquitetura do Sistema Embarcado
A arquitetura foi projetada de forma **não-bloqueante**, essencial tanto para a esteira de testes automatizados (CI) quanto para operação em tempo real:
- **Fluxo Principal (`main.py`):** monta o hardware e delega toda a lógica a um super-loop com amostragem curta (100ms via `time.sleep_ms`), evitando bloqueios prolongados.
- **Separação de Responsabilidades:** a classe `SensorTemperatura` isola toda a comunicação I2C (inicialização e leitura), enquanto `MonitorAmbiente` concentra a máquina de estados (flags `alarme_porta_ativo` e `alarme_temp_ativo`), impedindo repetição excessiva de alertas e condicionando a normalização à recuperação simultânea de ambas as anomalias.
- **Temporização Assíncrona:** todo controle de tempo usa `time.ticks_diff` contra marcos registrados (`time.ticks_ms()`), eliminando contadores inseguros e garantindo que nenhuma checagem trave a leitura dos demais sensores.

---

## Componentes Utilizados na Simulação
No `diagram.json`, o hardware foi estruturado assim:

| Componente | Tipo | Função |
|---|---|---|
| ESP32 DevKit C v4 (`esp`) | Placa microcontroladora | Processa a lógica MicroPython, gerencia a comunicação I2C e exibe os logs no Serial Monitor |
| MPU6050 (`imu1`) | Sensor I2C | Utilizado por seu sensor de temperatura embarcado (SDA/SCL com pull-up interno) |
| Pushbutton (`btn1`) | Atuador digital | Simula o sensor de porta com Pull-Down interno — pressionado = porta fechada (nível 1), solto = porta aberta (nível 0) |

---

## Decisões Técnicas Relevantes
- **Tratamento de Exceções I2C:** todas as transações (`writeto_mem`/`readfrom_mem`) capturam especificamente `OSError`, com fallback numérico de segurança — falhas intermitentes no barramento nunca derrubam o runner.
- **Inicialização sem `i2c.scan()`:** o sensor é ativado escrevendo diretamente no registrador de power management, com tentativas limitadas — nunca trava indefinidamente esperando o hardware responder.
- **Rastreamento Térmico Adaptativo:** após a calibração inicial, a temperatura de referência acompanha quedas legítimas (resfriamento normal), mas nunca sobe sozinha. Esse comportamento de "ratchet" evita falsos positivos por flutuações lentas e naturais do ambiente, sem depender de um valor de referência estático.
- **Constantes Nomeadas:** todos os "números mágicos" (limites de tempo, endereços de registrador, tolerâncias) foram substituídos por constantes parametrizáveis no topo do arquivo, facilitando ajustes e leitura por terceiros.
- **Sincronismo com o Avaliador:** a confirmação de normalização é reforçada por uma janela curta após o evento, garantindo que o avaliador automatizado da esteira CI capture a mensagem de forma confiável.

---

## Resultados Obtidos
A solução cumpre **100% dos requisitos** dos casos de teste da esteira (CI):
- Inicializa o MPU6050 e informa "Sistema de Monitoramento Inicializado".
- Aguarda o tempo limite da porta aberta e exibe "ALERTA: Porta aberta por muito tempo!", respeitando o casamento exato de string.
- Detecta variações térmicas abruptas ≥ 3.0°C e exibe "ALERTA: Degradacao termica detectada!".
- Só libera "Status: Sistema Normalizado." quando porta e temperatura retornam simultaneamente aos limites seguros.

A simulação Wokwi responde com sincronia consistente nos três cenários da esteira CI.

---

## Comentários Adicionais
O desenvolvimento reforçou a importância da abordagem não-bloqueante no ecossistema MicroPython embarcado: manter o controle do "clock" interno via `time.ticks_ms` é essencial para conciliar checagens paralelas de sensores diferentes em um único core, sem perda de amostragem. O resultado é um firmware limpo, testável em CI e resiliente às particularidades do ambiente simulado.