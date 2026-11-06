# Relatório inicial de auditoria GF117

Data da consulta: 2026-11-06. Repositórios consultados:

- [`nouveau-gf117-ci`](https://github.com/doc2605/nouveau-gf117-ci)
- [`nouveau-gf117-clock-ci`](https://github.com/doc2605/nouveau-gf117-clock-ci)

Este relatório registra o estado observado de branches, código e workflows; não
é uma validação física do notebook. As duas árvores usam uma fonte CachyOS
pinada para builds automatizados. Os resultados de harnesses simulados e de
compilação não são tratados como evidência de operação na GPU.

## `nouveau-gf117-ci`

- A branch `main` consultada estava em `a35ce1c` (`tools: pin core test helper to
  diagnostic build`). As branches experimentais
  `ci/gf117-disable-unverified-pwm-20261017` (`b9f5284`) e
  `ci/gf117-selected-pwm-20261017` (`60473c8`) não estavam incorporadas em
  `main`.
- O workflow da branch principal é
  [`.github/workflows/gf117-module.yml`](https://github.com/doc2605/nouveau-gf117-ci/blob/main/.github/workflows/gf117-module.yml).
  Ele executa no push para `main` ou por despacho manual, instala Clang/LLVM
  pinados e compila o módulo contra fonte/headers CachyOS através de
  `ci/build-gf117-module.sh`.
- A série da branch principal inclui os patches 0014–0016. O workflow chama
  `ci/build-gf117-module.sh`, que aplica todos os patches presentes no checkout;
  portanto, o run atual da série principal inclui 0014–0016. As
  branches posteriores investigam que o readback GF117 não estava comprovado,
  desabilitam esse caminho e acrescentam probes somente de leitura baseados em
  GF119. Portanto, não se deve apresentar o readback de PWM da série principal
  como medição validada. Os commits e runs posteriores documentam a investigação
  nas branches, não a validação da GPU.
- O HEAD da branch `main` está em `a35ce1c` e sua mensagem inclui `[skip ci]`.
  O último run verde encontrado para `main` é
  [38996866874](https://github.com/doc2605/nouveau-gf117-ci/actions/runs/38996866874),
  para o commit anterior `f5117af`; ele não valida o HEAD atual. As branches
  experimentais têm runs verdes, incluindo
  [39014502316](https://github.com/doc2605/nouveau-gf117-ci/actions/runs/39014502316)
  no commit `60473c8`, mas esses runs tampouco são evidência de operação física.
- Os testes `tools/test-gf117-*-source.py` compilam trechos extraídos do C real
  com substitutos para VBIOS, registradores ou hardware, frequentemente com
  UBSan. Isso é evidência de lógica de fonte sob mock. `tools/test-gf117-core-once.sh`
  é um procedimento de laboratório distinto, capaz de interagir com módulos e
  hardware; não é apropriado para CI automatizada.

## `nouveau-gf117-clock-ci`

- A branch de trabalho auditada para Rust é
  [`research/gf117-rust-pll`](https://github.com/doc2605/nouveau-gf117-clock-ci/tree/research/gf117-rust-pll),
  atualmente `c2e3ea2`. O clone de desenvolvimento possui também uma branch
  separada `research/rust-kbuild-poc`, divergente do remoto; ela não é a branch
  usada pelo workflow in-tree atual.
- O repositório contém a série GF117 0001–0022, testes de fonte e patches
  adicionais de segurança 0047–0050. A CI
  [`gf117-module.yml`](https://github.com/doc2605/nouveau-gf117-clock-ci/blob/research/gf117-rust-pll/.github/workflows/gf117-module.yml)
  constrói a série padrão de patches; não se deve confundi-la com
  [`gf117-rust-nouveau.yml`](https://github.com/doc2605/nouveau-gf117-clock-ci/blob/research/gf117-rust-pll/.github/workflows/gf117-rust-nouveau.yml),
  que aplica explicitamente os patches Rust e executa os harnesses adicionais.
- A prova Rust opt-in tem dois pontos de chamada no código Nouveau: validação
  escalar do diagnóstico `pstate_plan` e cálculo PLL do GF117 no caminho GF100.
  Depois de validar o cálculo em shadow, a alteração mais recente faz Rust
  produzir o resultado para GF117; C continua para outros chips e quando a
  opção está desligada. Harnesses cobrem retorno, coeficientes, C-only e erros,
  e o build pinned dessa promoção passou em `42220548739` (kernel CachyOS
  `09bc889a111715e4509b3819b628c9b9d9d09a0b`, commit do projeto
  `4b5e4f8e664a7612ed11879da68410b1f3f31fc8`). O artefato foi validado por
  digest externo, `unzip -t`, checksums internos e `zstd -t`. As funções Rust não
  recebem ponteiros, não interpretam estruturas VBIOS e não fazem MMIO. Ainda
  não há migração de ownership/lifecycle PCI/NVKM para Rust. O total líquido de
  linhas C específico do projeto ainda não foi reduzido: o solver C continua
  necessário para os outros chips e para builds sem a opção Rust.
- Os runs `42187920923`, `42190675638`, `42208371477` e `42209101812`
  compilaram o módulo Rust-enabled no kernel CachyOS fixado, com C/Rust
  linkados. Os hashes do módulo, configuração e `Module.symvers` são iguais
  entre os quatro runs. Os dois artefatos mais recentes tiveram ZIP íntegro,
  digest externo igual ao informado pela API do GitHub e `SHA256SUMS` aprovado.
  Isso não prova compatibilidade entre kernels/toolchains, carregamento,
  execução em hardware, desempenho ou segurança de reclocking.
- O run `42216528135` também concluiu com sucesso a compilação pinned e os
  testes ampliados, mas ainda usava o caminho PLL Rust em shadow.
- O run autoritativo `42220548739` compilou `vmlinux` e módulos com Rust e a
  opção GF117 ligada. O artefato `13505065977` (28,225,432 bytes) tem digest
  API `sha256:83c25ddec36f85ddcdfea45382d239ca78e75779a7f60f8713d199b6a0a73c0a`,
  igual ao ZIP baixado; `unzip -t`, todos os nove itens de `SHA256SUMS` e
  `zstd -t` passaram. O módulo descompactado tem SHA-256
  `e403fa16877e0d737365656a72a44e7576b63dd4df5ad7582c03eb288a1c2c73e` e
  vermagic `7.2.9-g09bc889a1117-dirty SMP preempt mod_unload modversions`.
  O config confirma `CONFIG_RUST`, Nouveau modular, opção GF117 Rust,
  `CONFIG_MODVERSIONS` e `CONFIG_EXTENDED_MODVERSIONS`; os dois símbolos Rust
  estão definidos no módulo, `gf100.o` referencia o solver PLL e o objeto Rust
  não tem referências indefinidas de panic; o relatório contém o thunk de
  kernel esperado `__x86_return_thunk`. Isso comprova build e ligação, não
  carregamento, execução ou comportamento em GPU.
- Os testes Rust/PLL reproduzem cálculos C e Rust em harness host e exercitam
  mismatch, limites, casos aleatórios e layout da ABI. São testes de lógica e
  integração de compilação; não são teste KUnit, load/unload ou operação da GPU.

## Estado de DKMS, hardware e decisão imediata

- A prova de Kbuild de módulo externo é um probe pequeno de C/Rust. Não
  demonstra que os headers CachyOS distribuídos contenham configuração,
  `Module.symvers` e artefatos Rust suficientes, nem que `dkms add/build/install/remove`
  funcione no ciclo real.
- DKMS não é, por princípio, incompatível com Rust: sua configuração permite
  escolher um comando `MAKE` customizado. A documentação do kernel, porém, exige
  que o build externo use Kbuild contra uma árvore preparada; com Rust e
  `CONFIG_MODVERSIONS`, a configuração e os arquivos de versão precisam suportar
  `CONFIG_EXTENDED_MODVERSIONS`. A combinação ainda precisa ser testada com os
  pacotes reais de kernel CachyOS.
- A extensão Nouveau desta branch modifica código interno do kernel e compila
  `nouveau.ko` dentro de uma árvore de kernel completa. O caminho sustentado pela
  evidência atual é patch + build Kbuild do kernel fixado; anunciar o pacote como
  DKMS funcional seria prematuro.
- A fronteira é importante: os dois objetos Rust entram no `nouveau.ko` existente
  e são chamados de `gf100.c` e do debugfs interno. Um DKMS separado não injeta
  objetos nesses call sites nem ganha acesso às estruturas privadas do NVKM.
  Empacotar outra cópia chamada `nouveau.ko` exigiria substituir/coordenar o
  módulo do kernel e acompanhar suas interfaces internas por kernel; isso é um
  pacote de kernel customizado, não um pequeno complemento DKMS independente.
- No ambiente de desenvolvimento consultado, o kernel em execução é
  `7.3.0-4-cachyos`, sem link `build` correspondente. Há árvores de headers para
  outros releases, mas a árvore 7.3.1 disponível expõe o `Kconfig` do Nouveau
  sem seu `Makefile`/`Kbuild` completo. Isso confirma que os headers instalados
  aqui não bastam para repetir a integração do Nouveau. É observação deste
  ambiente, não de todos os pacotes CachyOS.

## Integridade do artefato de teste físico

- A revisão de 2026-11-06 encontrou um pin antigo no helper físico para o run
  `39024214497`. Esse módulo não contém os guards 0048/0050 e não deve ser usado
  para um teste de clock. O helper não referencia mais esse artefato.
- O workflow `gf117-module.yml` agora aplica os patches 0047–0050 e grava seus
  hashes em `manifest.json`. `SHA256SUMS` cobre o módulo compactado, seu arquivo
  `.sha256` e o manifesto; o log de build fica fora da lista porque a própria
  verificação escreve nele.
- Para `--probe-only`, o helper exige um `.ko` descompactado, o hash externo
  informado em `GF117_MODULE_SHA256` e um manifesto ao lado (ou
  `GF117_MODULE_MANIFEST`). `tools/verify-gf117-artifact.py` confere kernel,
  hash do módulo e hashes locais de toda a série de patches C e dos patches de
  segurança. O artefato da CI é
  publicado como `nouveau.ko.zst`; deve ser extraído para
  `artifacts/gf117-module/nouveau.ko`, preservando `manifest.json` no mesmo
  diretório. A origem do SHA deve ser o manifesto do artefato baixado/verificado.
- `--apply` permanece bloqueado. É um teste físico que escreve estado de clock;
  não será liberado por um build verde sozinho. Ainda requer autorização
  explícita e revisão do artefato exato antes de qualquer execução.
- A CI de segurança ainda precisa ser executada sobre estas alterações. As
  verificações locais passaram para `git diff --check`, sintaxe Bash e o teste
  hermético do helper/verificador; isto não comprova compilação do módulo nem
  comportamento na GPU.
- Não foi feita instalação, alteração de initramfs, carregamento do módulo Rust,
  escrita de registradores, mudança de clocks/tensão/PWM, ou teste físico nesta
  auditoria. O estado e limites da investigação estática estão em
  [`docs/reverse-engineering/status.md`](reverse-engineering/status.md); não há
  análise do blob proprietário.
- Próximos gates: validar em CI a nova cobertura de hashes para todos os arquivos
  auxiliares de símbolos; manter leitura PWM separada de escrita e bloqueada
  quando a fonte não for independente; documentar suporte de build por kernel;
  só avaliar um ciclo DKMS com os pacotes de headers concretos; e reservar testes
  físicos para um procedimento explícito, reversível e autorizado.

## Avaliação dos componentes candidatos a Rust

| Componente | Decisão nesta etapa | Motivo e evidência necessária para avançar |
| --- | --- | --- |
| Estados GF117 e gerenciamento de energia | Manter em C/NVKM | Envolve estado do dispositivo, worker, serialização e sequência de transição. A prova Rust atual não possui ownership nem callbacks de ciclo de vida. Primeiro exigir contrato de estado e testes dos caminhos de falha. |
| Inicialização e desligamento | Manter em C/NVKM | A ordem e a liberação de recursos pertencem à integração existente do Nouveau. A abstração Rust PCI disponível não substitui a posse e o teardown de NVKM. |
| Validação escalar de tensão | Rust no diagnóstico | `target_uv/min_uv/max_uv` são escalares; a validação Rust já está ligada ao `pstate_plan` read-only e comparada ao fallback C. Mapear VID/VBIOS e qualquer transição continuam em C. |
| Cálculo PLL | Rust autoritativo para GF117, opt-in e experimental; build pinned aprovado | Rust calcula o candidato GF117 quando a opção está ativa; C continua para outros chips e builds com a opção desligada. O solver é escalar e não toca MMIO. O caminho de configuração/programação posterior ainda não tem teste físico. |
| Interpretação VBIOS | Manter parsing em C | Parsers Nouveau operam em estruturas e buffers com invariantes próprias. Extrair campos escalares em C para os validadores já existentes evita duplicar parser sem benefício de segurança comprovado. |
| Controle e validação PWM | Manter hardware em C; adiar lógica Rust | O getter 0022 combina leitura de hardware, rota de GPIO/VBIOS, parâmetros PWM e limites. A série principal e branches posteriores divergem sobre se esse readback GF117 é confiável; o harness mock testa a lógica, não o significado físico dos registradores. Reabrir após evidência read-only no hardware e manter leitura distinta de escrita. |
| Diagnóstico e estados de erro | Rust para lógica pura, C para integração | O validador de plano já demonstra a fronteira pequena. Debugfs, logs, locks e propagação a subsistemas continuam sob controle do Nouveau em C. |

Assim, a promoção atual se restringe à aritmética pura do PLL GF117, depois da
paridade diferencial contra o C patched e de build/artefato pinned validados. O
próximo avanço depende de validar novos kernels e integrar mais lógica segura.
A evidência não justifica
mover sequências MMIO, parser de BIOS, worker, ciclo de vida PCI/NVKM ou PWM
para Rust.

## Comparação da estratégia híbrida atual

| Critério | Evidência atual | Limite atual |
| --- | --- | --- |
| Segurança de memória | Funções Rust atuais recebem escalares e não usam `unsafe`, ponteiros ou alocação. | Segurança de memória da aritmética não comprova segurança elétrica ou de sequência de hardware. |
| Manutenção | Harness compara aritmética C/Rust e testa que GF117 usa Rust, chips não GF117 usam C e builds C-only mantêm o solver. Kconfig mantém Rust opt-in. | A declaração C e o tipo `#[repr(C)]` precisam continuar sincronizados; solver C segue necessário fora do GF117. |
| Compatibilidade | Build remoto pinado passou previamente em CachyOS 7.2.9-2, x86_64, Rust 1.85, bindgen 0.71.1 e Clang/LLVM. | Um kernel, arquitetura e toolchain não cobrem outras versões. Build não usa headers DKMS instalados. |
| Desempenho | PLL é cálculo escalar e sem I/O; na rota GF117 usa-se um cálculo. | Não há benchmark; nenhum custo de execução em hardware foi medido. |
| Custo de integração | Dois objetos entram no módulo existente; Kconfig depende de `RUST`, desativado por padrão; build remoto prepara a toolchain. | Requer árvore de kernel completa e patches na fonte Nouveau; não é um pequeno módulo DKMS independente. |

Essa comparação sustenta usar Rust para o PLL GF117 sob opção explícita e manter
C nos demais casos. Ainda não há redução líquida de C, pois o cálculo C é
compartilhado por outros chips. A meta de redução deve ser medida no código
específico do projeto, sem retirar suporte C necessário.

## Estado por fase do briefing

| Fase | Estado observado | Evidência/pendência principal |
| --- | --- | --- |
| 1. Auditoria dos dois repositórios | Auditoria inicial documentada | Branches e workflows comparados; continuar atualizando por commit/branch. |
| 2. Testes e CI | Parcialmente implementada | Harnesses host/source e workflow remoto pinned; quatro builds Rust-enabled passaram e artefatos foram comparados. A matriz ainda cobre uma versão de kernel e x86_64. |
| 3. Kernel moderno e DKMS | Estratégia escolhida; DKMS não comprovado | Integração Rust atual modifica árvore interna e requer Kbuild in-tree. Headers deste ambiente não contêm fonte/Kbuild completos do Nouveau. |
| 4. Proteções e inicialização | Guards de fonte existem; hardware pendente | Patches GF117 adicionam fail-closed em caminhos específicos; ausência de teste físico impede afirmar correção global de init. |
| 5. Sensores, PWM e tensão | Parcial e experimental | Diagnósticos e mocks existem; leitura GPIO/VID é tabela de comando, PWM GF117 segue controverso, sem medição de trilho confirmada. |
| 6. Gerenciamento de energia e clocks | Cálculos/documentação, sem RE proprietário | PLL tem paridade C/Rust host e rota Rust opt-in para GF117, compilada no kernel pinned; não há validação de execução em hardware. Análise do blob 390.157 não foi feita devido à restrição da licença. |
| 7. Reclocking | Experimental, sem promoção física | Código tem guards e preflight, mas não há validação de estabilidade/rollback em GPU. Nenhuma escrita foi executada. |
| 8. Testes físicos GT 720M | Não realizados nesta etapa | Exigem equipamento/ambiente adequados e autorização explícita para ações que alterem estado. |
| 9. Empacotamento e instalação | Documentação experimental; pacote ausente | Não há entrega DKMS funcional, instruções de instalação validadas ou compatibilidade de pacote por kernel. |

O build e a ligação de dois componentes Rust dentro de `nouveau.ko` foram
demonstrados em várias execuções pinned do caminho anterior. O build pinned
`42220548739` também valida a promoção da rota de cálculo PLL GF117 a Rust
quando a opção Kconfig está ativa. Isso não
representa um driver GF117 instalável ou validado em hardware, e não reduz
ainda o total líquido de C específico do projeto.

## Referências oficiais de build Rust

O guia oficial Linux 7.2 descreve `rustc`, `rust-src`, `bindgen`, libclang e o
target `make LLVM=1 rustavailable` como partes da verificação de suporte. A
documentação de módulos externos requer uma árvore/configuração kernel
preparada e `Module.symvers`; com `CONFIG_RUST` e `CONFIG_MODVERSIONS`, exige
`CONFIG_EXTENDED_MODVERSIONS`. Essas condições explicam por que um teste simples
de Kbuild ou um conjunto reduzido de headers não estabelece suporte DKMS.

A árvore CachyOS exata usada no build também traz exemplos de drivers Rust em
`samples/rust/`. `rust_driver_pci.rs` implementa `pci::Driver`, `probe` e
`unbind`, mapeia BAR e declara registradores tipados para o dispositivo de teste
QEMU `pci-testdev`. `rust_dma.rs` cobre `Coherent` e `SGTable`; contém chamadas e
implementações `unsafe` com justificativas locais de invariantes. São exemplos
reais do kernel e provam que essas APIs existem nesta árvore, mas exercitam um
dispositivo QEMU de teste, não uma GPU NVIDIA. O `unsafe` do exemplo DMA exige
avaliação caso a caso; não é precedência para usar as mesmas operações no NVKM.

- [Exemplo PCI no commit de kernel fixado](https://raw.githubusercontent.com/CachyOS/linux/09bc889a111715e4509b3819b628c9b9d9d09a0b/samples/rust/rust_driver_pci.rs)
- [Exemplo DMA no commit de kernel fixado](https://raw.githubusercontent.com/CachyOS/linux/09bc889a111715e4509b3819b628c9b9d9d09a0b/samples/rust/rust_dma.rs)
- [Exemplo PCI no upstream Linux](https://github.com/torvalds/linux/blob/master/samples/rust/rust_driver_pci.rs)
- [Exemplo DMA no upstream Linux](https://github.com/torvalds/linux/blob/master/samples/rust/rust_dma.rs)

- [Rust Quick Start — Linux 7.2](https://docs.kernel.org/7.2/rust/quick-start.html)
- [Building External Modules — Kbuild](https://docs.kernel.org/kbuild/modules.html)
- [DKMS README](https://github.com/dkms-project/dkms/blob/main/README.md)
- [PCI Rust API — Linux 7.2](https://rust.docs.kernel.org/7.2/kernel/pci/index.html)
- [MMIO Rust API — Linux 7.2](https://rust.docs.kernel.org/7.2/kernel/io/index.html)
- [DMA Rust API — Linux 7.2](https://rust.docs.kernel.org/7.2/kernel/dma/index.html)
