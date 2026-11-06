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
  escalar do diagnóstico `pstate_plan` e cálculo PLL de sombra no caminho GF100
  para chipset GF117. O segundo compara retorno e coeficientes com o cálculo C;
  em divergência, conserva o resultado C. As funções Rust não recebem ponteiros,
  não interpretam diretamente estruturas VBIOS e não fazem MMIO. Ainda não há
  migração de ownership/lifecycle PCI/NVKM para Rust. Nesta etapa experimental,
  Rust acrescenta novos objetos e não reduz ainda o total líquido de linhas C;
  a redução depende de migrar componentes após paridade e evidência de runtime.
- Os runs `42187920923` e `42190675638` compilaram o módulo Rust-enabled no
  kernel CachyOS fixado, com C/Rust linkados. Os bytes do módulo foram iguais
  entre esses dois runs para a mesma árvore/configuração/toolchain registrada.
  Isso não prova reprodutibilidade entre kernels/toolchains, carregamento,
  execução em hardware, desempenho ou segurança de reclocking. O run
  `42208371477`, para `c2e3ea2`, foi iniciado em 2026-11-06 e ainda estava em
  andamento no momento desta consulta; verificar o resultado final antes de
  atualizar o relatório.
- Os testes Rust/PLL reproduzem cálculos C e Rust em harness host e exercitam
  mismatch, limites, casos aleatórios e layout da ABI. São testes de lógica e
  integração de compilação; não são teste KUnit, load/unload ou operação da GPU.

## Estado de DKMS, hardware e decisão imediata

- A prova de Kbuild de módulo externo é um probe pequeno de C/Rust. Não
  demonstra que os headers CachyOS distribuídos contenham configuração,
  `Module.symvers` e artefatos Rust suficientes, nem que `dkms add/build/install/remove`
  funcione no ciclo real.
- A extensão Nouveau desta branch modifica código interno do kernel e compila
  `nouveau.ko` dentro de uma árvore de kernel completa. O caminho sustentado pela
  evidência atual é patch + build Kbuild do kernel fixado; anunciar o pacote como
  DKMS funcional seria prematuro.
- Não foi feita instalação, alteração de initramfs, carregamento do módulo Rust,
  escrita de registradores, mudança de clocks/tensão/PWM, ou teste físico nesta
  auditoria. Não há relatório de engenharia reversa baseado em execução do blob
  proprietário anexado a esta prova Rust.
- Próximos gates: confirmar o run `42208371477`; manter leitura PWM separada de
  escrita e bloqueada quando a fonte não for independente; documentar suporte
  de build por kernel; só avaliar um ciclo DKMS com os pacotes de headers
  concretos; e reservar testes físicos para um procedimento explícito, reversível
  e autorizado.

## Referências oficiais de build Rust

O guia oficial Linux 7.2 descreve `rustc`, `rust-src`, `bindgen`, libclang e o
target `make LLVM=1 rustavailable` como partes da verificação de suporte. A
documentação de módulos externos requer uma árvore/configuração kernel
preparada e `Module.symvers`; com `CONFIG_RUST` e `CONFIG_MODVERSIONS`, exige
`CONFIG_EXTENDED_MODVERSIONS`. Essas condições explicam por que um teste simples
de Kbuild ou um conjunto reduzido de headers não estabelece suporte DKMS.

- [Rust Quick Start — Linux 7.2](https://docs.kernel.org/7.2/rust/quick-start.html)
- [Building External Modules — Kbuild](https://docs.kernel.org/kbuild/modules.html)
- [PCI Rust API — Linux 7.2](https://rust.docs.kernel.org/7.2/kernel/pci/index.html)
- [MMIO Rust API — Linux 7.2](https://rust.docs.kernel.org/7.2/kernel/io/index.html)
- [DMA Rust API — Linux 7.2](https://rust.docs.kernel.org/7.2/kernel/dma/index.html)
