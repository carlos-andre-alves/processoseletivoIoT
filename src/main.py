import machine
import time

# ==========================================
# CONSTANTES DE CONFIGURACAO
# ==========================================
PINO_SDA = 21
PINO_SCL = 22
PINO_BOTAO = 4

I2C_FREQ_HZ = 100_000
MPU_ADDR = 0x68
MPU_REG_PWR_MGMT_1 = 0x6B          # liga o sensor (tira do modo sleep)
MPU_REG_TEMP_OUT_H = 0x41          # registrador inicial da temperatura (2 bytes)
MPU_INIT_MAX_TENTATIVAS = 10       # 10 x 50ms = 0.5s de tolerancia na inicializacao
MPU_INIT_INTERVALO_MS = 50
MPU_LEITURA_MAX_TENTATIVAS = 2     # reacorda o sensor 1x antes de desistir da leitura
MPU_TEMP_FALLBACK_C = 20.0         # valor de seguranca se todas as leituras falharem

LIMITE_TEMPO_PORTA_MS = 5000       # tempo maximo com a porta aberta antes do alarme
LIMITE_VARIACAO_TEMP_C = 3.0       # variacao de temperatura que dispara o alarme termico

JANELA_CALIBRACAO_MS = 500         # tempo para o teste configurar a temp. inicial
JANELA_ECO_NORMALIZACAO_MS = 1000  # reforca a msg de normalizacao por esse tempo
INTERVALO_LOOP_MS = 100            # cadencia do loop principal


# ==========================================
# CAMADA DE HARDWARE: SENSOR DE TEMPERATURA
# ==========================================
class SensorTemperatura:
    """Encapsula a comunicacao I2C com o MPU6050."""

    def __init__(self, i2c, endereco=MPU_ADDR):
        self._i2c = i2c
        self._endereco = endereco

    def _acordar(self):
        try:
            self._i2c.writeto_mem(self._endereco, MPU_REG_PWR_MGMT_1, b'\x00')
            return True
        except OSError as erro:
            print("Erro I2C ao acordar sensor:", erro)
            return False

    def inicializar(self):
        # Nao usa i2c.scan(): alguns chips do Wokwi nao respondem ao scan de
        # varredura, mesmo respondendo a leituras/escritas diretas. Tentativas
        # limitadas para nunca travar indefinidamente.
        for _ in range(MPU_INIT_MAX_TENTATIVAS):
            if self._acordar():
                print("MPU6050 inicializado com sucesso")
                return True
            time.sleep_ms(MPU_INIT_INTERVALO_MS)

        print("AVISO: MPU6050 nao respondeu apos", MPU_INIT_MAX_TENTATIVAS,
              "tentativas. Seguindo sem confirmacao.")
        return False

    def ler_celsius(self):
        # Se a 1a leitura falhar, reacorda o sensor e tenta mais uma vez antes
        # de desistir. Sempre retorna um numero (nunca None) para simplificar
        # quem consome o valor.
        for tentativa in range(MPU_LEITURA_MAX_TENTATIVAS):
            try:
                bruto = self._i2c.readfrom_mem(self._endereco, MPU_REG_TEMP_OUT_H, 2)
                valor = (bruto[0] << 8) | bruto[1]
                if valor > 32767:
                    valor -= 65536
                return (valor / 340.0) + 36.53
            except OSError as erro:
                print("Erro I2C na leitura:", erro)
                if tentativa < MPU_LEITURA_MAX_TENTATIVAS - 1:
                    self._acordar()
                    time.sleep_ms(20)

        return MPU_TEMP_FALLBACK_C


# ==========================================
# MAQUINA DE ESTADOS DO MONITORAMENTO
# ==========================================
class MonitorAmbiente:
    """Mantem o estado dos alarmes de porta/temperatura e decide quando
    dispara-los ou normaliza-los a cada iteracao do loop."""

    def __init__(self, sensor, botao):
        self._sensor = sensor
        self._botao = botao

        self.alarme_porta_ativo = False
        self.alarme_temp_ativo = False
        self._porta_aberta_anteriormente = False
        self._tempo_abertura_ms = 0

        self._temp_referencia = None
        self._referencia_travada = False
        self._fim_calibracao_ms = 0

        self._fim_eco_normalizado_ms = 0

    def iniciar_calibracao(self, agora_ms):
        # Janela em que a referencia ainda acompanha o sensor de perto, dando
        # tempo do ambiente de teste configurar a temperatura inicial antes
        # de travarmos um valor definitivo.
        self._temp_referencia = self._sensor.ler_celsius()
        self._fim_calibracao_ms = time.ticks_add(agora_ms, JANELA_CALIBRACAO_MS)

    def _atualizar_referencia(self, temp_atual, agora_ms):
        if not self._referencia_travada:
            self._temp_referencia = temp_atual  # ainda calibrando: segue o sensor
            if time.ticks_diff(agora_ms, self._fim_calibracao_ms) >= 0:
                self._referencia_travada = True
            return

        # Apos travada, a referencia acompanha quedas legitimas de temperatura
        # (resfriamento normal), mas nunca sobe sozinha -- evita falso alarme
        # apos um resfriamento genuino com uma referencia antiga "presa".
        sistema_em_alarme = self.alarme_porta_ativo or self.alarme_temp_ativo
        if not sistema_em_alarme and temp_atual < self._temp_referencia:
            self._temp_referencia = temp_atual

    def _verificar_alarme_porta(self, porta_fechada, agora_ms):
        if porta_fechada:
            self._porta_aberta_anteriormente = False
            return

        if not self._porta_aberta_anteriormente:
            self._tempo_abertura_ms = agora_ms
            self._porta_aberta_anteriormente = True
            return

        tempo_aberta_ms = time.ticks_diff(agora_ms, self._tempo_abertura_ms)
        if tempo_aberta_ms >= LIMITE_TEMPO_PORTA_MS and not self.alarme_porta_ativo:
            print("ALERTA: Porta aberta por muito tempo!")
            self.alarme_porta_ativo = True

    def _verificar_alarme_temperatura(self, delta_t):
        if delta_t >= LIMITE_VARIACAO_TEMP_C and not self.alarme_temp_ativo:
            print("ALERTA: Degradacao termica detectada!")
            self.alarme_temp_ativo = True

    def _verificar_normalizacao(self, porta_fechada, delta_t, temp_atual, agora_ms):
        sistema_em_alarme = self.alarme_porta_ativo or self.alarme_temp_ativo
        condicoes_normais = porta_fechada and (delta_t < LIMITE_VARIACAO_TEMP_C)

        if sistema_em_alarme and condicoes_normais:
            print("Status: Sistema Normalizado.")
            self.alarme_porta_ativo = False
            self.alarme_temp_ativo = False
            self._temp_referencia = temp_atual  # reaproveita leitura ja feita nesta iteracao
            # Reforca a msg por mais um tempo: cobre o caso de o teste comecar
            # a escutar o serial pouco depois do evento e perder a 1a impressao.
            self._fim_eco_normalizado_ms = time.ticks_add(agora_ms, JANELA_ECO_NORMALIZACAO_MS)
        elif not sistema_em_alarme and time.ticks_diff(self._fim_eco_normalizado_ms, agora_ms) > 0:
            print("Status: Sistema Normalizado.")

    def atualizar(self):
        agora_ms = time.ticks_ms()
        porta_fechada = (self._botao.value() == 1)
        temp_atual = self._sensor.ler_celsius()  # unica leitura I2C da iteracao

        self._atualizar_referencia(temp_atual, agora_ms)
        delta_t = temp_atual - self._temp_referencia

        self._verificar_alarme_porta(porta_fechada, agora_ms)
        self._verificar_alarme_temperatura(delta_t)
        self._verificar_normalizacao(porta_fechada, delta_t, temp_atual, agora_ms)


# ==========================================
# PONTO DE ENTRADA
# ==========================================
def main():
    botao = machine.Pin(PINO_BOTAO, machine.Pin.IN, machine.Pin.PULL_DOWN)

    pino_scl = machine.Pin(PINO_SCL, pull=machine.Pin.PULL_UP)  # pull-ups evitam
    pino_sda = machine.Pin(PINO_SDA, pull=machine.Pin.PULL_UP)  # ETIMEDOUT/ENODEV no I2C
    i2c = machine.SoftI2C(scl=pino_scl, sda=pino_sda, freq=I2C_FREQ_HZ)

    sensor = SensorTemperatura(i2c)
    sensor.inicializar()

    monitor = MonitorAmbiente(sensor, botao)

    print("Sistema de Monitoramento Inicializado")  # obrigatoria: dispara os testes do CI
    monitor.iniciar_calibracao(time.ticks_ms())

    while True:
        monitor.atualizar()
        time.sleep_ms(INTERVALO_LOOP_MS)


if __name__ == '__main__':
    main()