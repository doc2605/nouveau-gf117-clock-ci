# Prova de conceito C + Rust para validação GF117

Estado: **protótipo de integração, não integrante do Nouveau e não validado no kernel**. O componente `limits.rs` é `no_std`, sem alocação, MMIO, ponteiros ou blocos `unsafe`; recebe apenas inteiros e devolve um código. `glue.c` o chama a partir de um módulo Kbuild composto. Esse módulo não manipula hardware. Não instalar nem carregar o módulo para esta investigação.

`./test-host.sh` compila Rust em objeto, liga com C e compara uma implementação C de referência em 1.728 combinações de limites. Esse teste verifica ABI e lógica no host, não a compilação ou execução no kernel. O teste usa arquivos temporários e não requer Cargo.

Quando houver uma árvore/configuração de kernel apropriada, o comando de build remoto a validar é `make -C "$KDIR" M="$PWD" modules`. O Makefile é uma hipótese de integração baseada nas regras Kbuild da tag CachyOS `cachyos-7.2.9-2`, ainda **não verificada com Kbuild**. Antes de executá-lo é preciso verificar `CONFIG_RUST=y`, artefatos Rust preparados, `Module.symvers` quando necessário, toolchain compatível e o resultado de `make rustavailable` na mesma árvore. Não usar `modules_install`. A integração real ao Nouveau deve acrescentar o objeto Rust ao `nouveau-y` apenas em configuração experimental apropriada e chamar o validador no caminho de produção, com fallback C definido e testes de equivalência. Nada disso está demonstrado ainda.

A função não determina se uma tensão física é segura. Não usar seu resultado para programar clock, PWM ou tensão sem validar independentemente as entradas e o comportamento do hardware. Limites aqui são apenas parâmetros de teste, não limites do GF117.
