import machine
import time

# ==========================================
# CONSTANTES E PARÂMETROS DE CONFIGURAÇÃO
# ==========================================
LIMITE_TEMPO_PORTA_MS = 5000     # Tempo máximo de porta aberta (X)
LIMITE_VARIACAO_TEMP_C = 3.0     # Variação máxima permitida (Y)
MPU_ADDR = 0x68                  # Endereço I2C padrão do MPU6050
PINO_BOTAO = 4                   # Pino de leitura do botão (Porta)

# ==========================================
# CONFIGURAÇÃO DE HARDWARE
# ==========================================
# Botão conectado ao 3V3. Usamos PULL_DOWN interno.
# Conforme edital: Pressionado/Fechado = 1 | Solto/Aberto = 0
botao = machine.Pin(PINO_BOTAO, machine.Pin.IN, machine.Pin.PULL_DOWN)

# Barramento I2C para comunicação com o MPU6050
i2c = machine.SoftI2C(scl=machine.Pin(22), sda=machine.Pin(21))

# ==========================================
# FUNÇÕES DE ABSTRAÇÃO (CLEAN CODE)
# ==========================================
def init_mpu():
    """Acorda o MPU6050 desativando o modo sleep no registrador 0x6B."""
    i2c.writeto_mem(MPU_ADDR, 0x6B, b'\x00')

def ler_temperatura():
    """Lê os registradores de temperatura (0x41 e 0x42) e converte para Celsius."""
    raw = i2c.readfrom_mem(MPU_ADDR, 0x41, 2)
    # Operadores bitwise para montar o inteiro de 16 bits
    val = (raw[0] << 8) | raw[1]
    if val > 32767:
        val -= 65536
    # Fórmula padrão de conversão descrita no datasheet do MPU6050
    return (val / 340.0) + 36.53


# ROTINA PRINCIPAL (MAIN)

def main():
    # 1. Inicializa o hardware via I2C nativo
    init_mpu()
    
    # 2. Variáveis de Máquina de Estado
    alarme_porta_ativo = False
    alarme_temp_ativo = False
    porta_aberta_anteriormente = False
    tempo_abertura_ms = 0
    
    # 3. Estabilização e cálculo da linha de base térmica (T_referencia)
    time.sleep_ms(500)
    temp_referencia = ler_temperatura()

    # Log estrito de inicialização OBRIGATÓRIO
    print("Sistema de Monitoramento Inicializado")

    # Loop Principal Não-Bloqueante
    while True:
        # A. Leitura de Sensores e Tempo Contínuo
        porta_fechada = (botao.value() == 1)
        temp_atual = ler_temperatura()
        tempo_atual = time.ticks_ms()

        # B. Lógica de Tempo de Porta Aberta
        if not porta_fechada:
            if not porta_aberta_anteriormente:
                # Porta acabou de abrir, crava o carimbo de tempo
                tempo_abertura_ms = tempo_atual
                porta_aberta_anteriormente = True
            else:
                # Porta continuou aberta, verifica a exposição
                tempo_decorrido = time.ticks_diff(tempo_atual, tempo_abertura_ms)
                if tempo_decorrido >= LIMITE_TEMPO_PORTA_MS and not alarme_porta_ativo:
                    print("ALERTA: Porta aberta por muito tempo!")
                    alarme_porta_ativo = True
        else:
            # Porta foi fechada
            porta_aberta_anteriormente = False

        # C. Lógica de Degradação Térmica (Gradiente)
        delta_t = temp_atual - temp_referencia
        if delta_t >= LIMITE_VARIACAO_TEMP_C and not alarme_temp_ativo:
            print("ALERTA: Degradacao termica detectada!")
            alarme_temp_ativo = True

        # D. Lógica de Normalização de Sistema
        # O sistema exige que AMBAS condições estejam seguras para desligar o alarme
        if alarme_porta_ativo or alarme_temp_ativo:
            if porta_fechada and (delta_t < LIMITE_VARIACAO_TEMP_C):
                print("Status: Sistema Normalizado.")
                alarme_porta_ativo = False
                alarme_temp_ativo = False
                # Reseta a referência térmica para o ambiente atual normalizado
                temp_referencia = ler_temperatura()

        # Ciclo de delay muito rápido e não-bloqueante (100ms)
        time.sleep_ms(100)

if __name__ == '__main__':
    main()