# Escopo e estado da engenharia reversa GF117

Consulta em 2026-11-06. Esta nota separa evidência aberta e local de qualquer
afirmação sobre o driver NVIDIA proprietário.

## Pacote NVIDIA local

Foi identificado um pacote Linux x86_64 NVIDIA 390.157 para consulta somente de
metadados/licença, SHA-256
`162317a49aa5a521eb888ec12119bfe5a45cec4e8653efc575a2d04fb05bf581`. O
instalador não foi executado. A licença foi lida sem carregar nem desmontar o
objeto do driver. A seção 2.1.3 da licença oficial proíbe engenharia reversa,
descompilação e desmontagem; portanto, este projeto não aplicou Ghidra,
`objdump`, `readelf` nem outras ferramentas de análise ao binário. Esta é uma
decisão conservadora de escopo do projeto, não uma conclusão jurídica sobre
possíveis exceções legais.

Fontes oficiais:

- [Licença NVIDIA 390.157](https://download.nvidia.com/XFree86/Linux-x86_64/390.157/license.txt)
- [Índice oficial do pacote 390.157](https://download.nvidia.com/XFree86/Linux-x86_64/390.157/)
- [Lista oficial de GPUs suportadas pelo driver 390.157](https://download.nvidia.com/XFree86/Linux-x86_64/390.157/README/supportedchips.html)

A lista oficial inclui vários sistemas GeForce GT 720M com PCI ID `1140` e
subsystem IDs distintos. A própria NVIDIA adverte que a presença da GPU na
lista não garante compatibilidade do desenho de notebook híbrido: há casos que
dependem de uma forma de desativar a GPU integrada. Isso não identifica a placa
específica do projeto nem comprova o fluxo de inicialização dela.

## Evidência disponível sem o blob proprietário

- A busca local não encontrou ROM/VBIOS específica GF117 disponível para esta
  análise. Nenhum firmware foi carregado, modificado ou executado.
- O código aberto Nouveau e os patches documentam caminhos de VBIOS, GPIO/VID,
  PLL, RAMMAP e PWM. Esses caminhos descrevem o comportamento implementado no
  Nouveau; não são observações do driver proprietário.
- `nvkm_voltgpio_get` lê pinos VID para selecionar um valor da tabela de tensão
  do driver. Isso não mede independentemente a tensão física do trilho. O patch
  de guarda 0050 mantém o preflight GF117 bloqueado para esse backend.
- O readback PWM GF117 continua experimental. Patches posteriores desligam o
  caminho não verificado e investigam leitura baseada em GF119. Testes de fonte
  e mocks não confirmam o mapeamento elétrico nem o significado dos registradores
  na placa real.

## Próxima investigação permitida

Continuar com análise estática do código aberto Nouveau e das séries de patches:
mapear entrada VBIOS → plano/validação → callbacks e efeitos de hardware;
registrar arquivos, condições e resultados observáveis; rotular inferências; e
comparar somente com especificações/documentação pública autorizadas. Uma ROM
específica obtida licitamente poderá ser analisada como dados, sem executar
firmware, quando a origem e as permissões forem verificadas. Qualquer acesso
físico que altere clocks, tensão, ventoinha ou energia continua sujeito a
autorização explícita e a um procedimento de rollback.
