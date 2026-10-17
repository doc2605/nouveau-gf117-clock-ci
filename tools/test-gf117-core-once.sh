#!/usr/bin/env bash
# Teste físico explícito GF117: carga temporária, sem instalar módulo.
set -euo pipefail
probe_only=0
case "${1:-}" in
    --help|-h|'')
        echo "Uso: bash $0 --probe-only (execute como root)"
        echo "Lê GPIO/PWM candidato, sem solicitar mudança de clock."
        echo "O módulo é trocado temporariamente; init/teardown ainda acessam MMIO."
        echo "Teste de clock indisponível: tensão PWM da GF117 ainda não tem backend validado."
        exit 0 ;;
    --probe-only) [[ $# == 1 ]] || exit 2; probe_only=1 ;;
    --apply)
        [[ $# == 1 ]] || exit 2
        echo "Teste de clock bloqueado antes de descarregar o driver: VBIOS usa PWM e o backend GF117 de tensão não foi implementado/validado." >&2
        echo "O preflight atual retorna -ENODEV; use --probe-only para coletar o diagnóstico PWM." >&2
        exit 2 ;;
    *) echo "Argumento inválido; use --help" >&2; exit 2 ;;
esac
[[ $EUID == 0 ]] || { echo "Execute como root (ou invoque com sudo)." >&2; exit 2; }
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
caller_home=$(getent passwd "${SUDO_UID:-$(id -u)}" | cut -d: -f6)
caller_home=${caller_home:-$HOME}
repo_root=${GF117_REPO_ROOT:-}
if [[ -z "$repo_root" ]]; then
    if [[ -d "$script_dir/../artifacts" ]]; then
        repo_root=$(cd "$script_dir/.." && pwd)
    elif [[ -d "$caller_home/Nvidia-GT720M-Fix-atualizado/artifacts" ]]; then
        repo_root="$caller_home/Nvidia-GT720M-Fix-atualizado"
    else
        echo "Checkout GF117 não encontrado; defina GF117_REPO_ROOT." >&2
        exit 1
    fi
fi
module="$repo_root/artifacts/local-build-20261017-pwm-route/nouveau.ko"
expected_hash=a1e07e28b549887a142dae9d418bcaf57281b55469b9cec5d35d5cc4be840a6d
device=/sys/bus/pci/devices/0000:08:00.0
debugfs=/sys/kernel/debug/dri/0000:08:00.0
hwmon_root=/sys/class/hwmon
temperature_path=
temperature_source=
log_dir=${GF117_TEST_LOG_DIR:-$caller_home/teste-logs}
loaded_srcversion_path=/sys/module/nouveau/srcversion
home_owner=$(stat -c '%u:%g' "$caller_home")
install -d -m 0755 -o "${home_owner%:*}" -g "${home_owner#*:}" "$log_dir"
log_file="$log_dir/clock-$(date +%Y%m%d-%H%M%S-%N).log"
touch "$log_file"; chown "$home_owner" "$log_file"; chmod 0644 "$log_file"
exec > >(tee -a "$log_file") 2>&1
echo "log: $log_file"
echo "started: $(date --iso-8601=seconds)"
if (( probe_only )); then
    echo "SONDA SEM PEDIDO DE P-STATE/CLOCK; init/teardown do módulo ainda acessam MMIO"
else
    echo "TESTE FÍSICO: núcleo VBIOS 0f, RAM preservada, noaccel=1, runpm=0"
fi
stock_removed=0
custom_loaded=0
clock_attempted=0
clocks_restored=0
reboot_needed=0
run_cursor=''
original_noaccel=0
original_runpm=-1
original_config=''
kernel_fault_pattern='nouveau.*(FAULT|timeout|failed|error)|WARNING:|BUG:|Oops:|general protection fault|soft lockup|hard LOCKUP|CTXSW_TIMEOUT|PRIVRING'
stock_vga_pattern='^.*nouveau 0000:08:00\.0: bus: MMIO write of [[:xdigit:]]{6}1f FAULT at 6013d4 \[ PRIVRING \]$'

# Stock GF117 GR init uses nvkm_mask(TPC_UNIT(0,0,0x05c),1,1).
# A failed read can produce badf1000, then the mask writes badf1001.
# This exception applies ONLY to the already removed original module.
stock_gr_pattern='^.*nouveau 0000:08:00\.0: bus: MMIO write of badf1001 FAULT at 50405c \[ PRIVRING \]$'

get_cursor() {
    journalctl -k -n 1 --show-cursor --no-pager -o cat |
        sed -n 's/^-- cursor: //p'
}
new_kernel_log() {
    journalctl -k --after-cursor "$1" --no-pager -o short-iso
}
check_faults() {
    local cursor=$1 lines result
    if ! lines=$(new_kernel_log "$cursor"); then
        echo "Falha lendo o journal; estado de faults não verificável." >&2
        return 1
    fi
    # No early-exit pipe: with pipefail, rg -q could give printf SIGPIPE and
    # turn a positive fault match into a false negative on a large journal.
    if rg -i "$kernel_fault_pattern" <<< "$lines" >/dev/null; then
        echo "Novos faults/erros do kernel; interrompendo o teste."
        printf '%s\n' "$lines"
        return 1
    else
        result=$?
        if (( result != 1 )); then
            echo "Falha pesquisando faults; teste interrompido." >&2
            return 1
        fi
    fi
}
check_stock_unload_faults() {
    local lines events unexpected count gr_count result
    (( stock_removed && !custom_loaded )) || return 1
    if ! lines=$(new_kernel_log "$1"); then
        echo "Falha lendo journal da remoção original." >&2; return 1
    fi
    if events=$(rg -i "$kernel_fault_pattern" <<< "$lines"); then
        :
    else
        result=$?
        if (( result == 1 )); then return 0; fi
        echo "Falha pesquisando journal original." >&2; return 1
    fi
    if unexpected=$(rg -vi "$stock_vga_pattern|$stock_gr_pattern" <<< "$events"); then
        echo "Erro inesperado removendo o módulo original; teste interrompido."
        printf '%s\n' "$lines"
        return 1
    else
        result=$?
        (( result == 1 )) || return 1
    fi
    if count=$(rg -ci "$stock_vga_pattern" <<< "$events"); then :; else
        result=$?; (( result == 1 )) || return 1; count=0
    fi
    if gr_count=$(rg -ci "$stock_gr_pattern" <<< "$events"); then :; else
        result=$?; (( result == 1 )) || return 1; gr_count=0
    fi
    if (( count <= 2 && gr_count <= 1 && count + gr_count >= 1 )); then
        echo "Falhas conhecidas do módulo ORIGINAL durante a remoção (VGA=$count GR=$gr_count):"
        printf '%s\n' "$events"
        echo "GR original não corrigido: o teste usa noaccel=1. Qualquer fault experimental continua fatal."
        return 0
    fi
    echo "Erro inesperado removendo o módulo original; teste interrompido."
    printf '%s\n' "$lines"
    return 1
}

check_voltage_plan() {
    local state line
    state=$(awk '/ requested_core_khz=775000 / { print $1 }' <<< "$plan")
    [[ "$state" =~ ^state=[0-9]+$ ]] || {
        echo "Estado alvo ausente ou ambíguo no preflight de tensão." >&2; return 1;
    }
    line=$(awk -v state="$state" '$1==state && $2 ~ /^voltage_uv=/ { print }' <<< "$plan")
    echo "voltage_preflight: $line"
    [[ "$line" =~ ^state=[0-9]+\ voltage_uv=[1-9][0-9]*\ target_uv=[1-9][0-9]*\ voltage_ready=1\ voltage_temp_c=[0-9]+$ ]] || {
        echo "Regulador/tensão alvo indisponível. Nenhum clock será solicitado." >&2
        return 1
    }
}

verify_loaded_module_srcversion() {
    local loaded_srcversion
    [[ -r "$loaded_srcversion_path" ]] || {
        echo "srcversion do módulo carregado indisponível." >&2; return 1;
    }
    loaded_srcversion=$(<"$loaded_srcversion_path")
    echo "loaded_srcversion=$loaded_srcversion"
    [[ "$loaded_srcversion" == "$module_srcversion" ]] || {
        echo "O srcversion carregado não corresponde ao artefato; teste interrompido." >&2
        return 1
    }
}

check_gpu_idle() {
    local node=$1 errors result
    errors=$(mktemp) || return 1
    if fuser "$node" >/dev/null 2>"$errors"; then
        rm -f "$errors"
        echo "GPU ocupada: $node"
        fuser -v "$node" || true
        echo "Feche os processos indicados; execute no TTY."
        return 1
    else
        result=$?
        # fuser uses 1 for both no users and some errors. Require empty
        # stderr as well, rather than treating every failure as an idle GPU.
        if (( result != 1 )) || [[ -s "$errors" ]]; then
            echo "Não foi possível verificar o uso da GPU: $node" >&2
            cat "$errors" >&2
            rm -f "$errors"
            return 1
        fi
    fi
    rm -f "$errors"
}

read_clocks() {
    local values
    if ! values=$(cat "$debugfs/pstate_current"); then
        echo "Falha lendo clocks; amostra parcial descartada." >&2; return 1
    fi
    core=$(awk '$1=="core" && $3=="MHz" {print $2; exit}' <<< "$values")
    memory=$(awk '$1=="memory" && $3=="MHz" {print $2; exit}' <<< "$values")
    [[ "$core" =~ ^[0-9]+$ && "$memory" =~ ^[0-9]+$ ]] || {
        echo "Leitura de clocks inválida: $values" >&2; return 1;
    }
    echo "measured: core=$core MHz memory=$memory MHz"
}
# Kernel p-state work is scheduled asynchronously. Do not treat the first
# read immediately after a request as proof that the transition has finished.
wait_target_clock() {
    local minimum=$1 maximum=$2 attempt
    for attempt in {1..20}; do
        read_clocks || return 1
        (( memory == memory_before )) || {
            echo "Memória mudou durante a transição." >&2; return 1;
        }
        check_faults "$load_cursor" || return 1
        read_temperature || return 1
        if (( core >= minimum && core <= maximum )); then
            return 0
        fi
        sleep 0.2
    done
    echo "Clock alvo não confirmado após a espera limitada." >&2
    return 1
}

select_temperature() {
    local path name label path_input
    local candidates=()
    for path in "$device"/hwmon/hwmon*/temp1_input; do
        if [[ -r "$path" ]]; then
            temperature_path=$path
            temperature_source=nouveau
            echo "temperature_source=$temperature_source path=$temperature_path"
            return 0
        fi
    done
    # Dell EC reports GPU sensors separately from CPU/Ambient. Require an
    # exact GPU label and exactly one candidate; never substitute CPU heat.
    for path in "$hwmon_root"/hwmon*; do
        [[ -r "$path/name" ]] || continue
        name=$(cat "$path/name")
        [[ "$name" == dell_smm ]] || continue
        for label in "$path"/temp*_label; do
            [[ -r "$label" ]] || continue
            [[ "$(cat "$label")" == GPU ]] || continue
            path_input="${label%_label}_input"
            [[ -r "$path_input" ]] && candidates+=("$path_input")
        done
    done
    if (( ${#candidates[@]} != 1 )); then
        echo "Temperatura GPU indisponível ou ambígua: ${#candidates[@]} sensores Dell GPU." >&2
        return 1
    fi
    temperature_path=${candidates[0]}
    temperature_source=dell_smm:GPU
    echo "temperature_source=$temperature_source path=$temperature_path"
}
read_temperature() {
    [[ -n "$temperature_path" ]] || select_temperature
    [[ -r "$temperature_path" ]] || { echo "Sensor GPU desapareceu." >&2; return 1; }
    if ! temperature=$(cat "$temperature_path"); then
        echo "Falha lendo a temperatura GPU." >&2; return 1
    fi
    [[ "$temperature" =~ ^[0-9]+$ ]] && (( temperature > 0 && temperature < 80000 )) || {
        echo "Temperatura inválida ou acima do limite de teste (80 C): $temperature" >&2
        return 1
    }
    echo "temperature_source=$temperature_source temperature_millicelsius=$temperature"
}

finish() {
    local status=$?
    trap - EXIT INT TERM
    if (( reboot_needed || (clock_attempted && !clocks_restored) )); then
        echo "Estado não confirmado. Não vou tentar outra transição ou descarregar o módulo."
        echo "Reinicie o notebook antes de outro teste: sudo reboot"
        status=1
    else
        if (( custom_loaded )); then
            echo "Descarregando o módulo de teste (sem aceleração)."
            if timeout --kill-after=2s 15s rmmod nouveau; then
                custom_loaded=0
            else
                echo "Falha/timeout na remoção. Reinicie: sudo reboot"
                reboot_needed=1; status=1
            fi
        fi
        if (( stock_removed && !reboot_needed )); then
            echo "stage=stock-restore"
            echo "Restaurando o Nouveau original."
            if modprobe nouveau "noaccel=$original_noaccel" "runpm=$original_runpm" "config=$original_config"; then
                stock_removed=0
            else
                echo "Falha ao restaurar. Reinicie: sudo reboot"
                status=1
            fi
        fi
    fi
    if [[ -n "$run_cursor" ]]; then
        echo "journal do teste:"
        new_kernel_log "$run_cursor" || true
    fi
    echo "finished: $(date --iso-8601=seconds), exit=$status"
    exit "$status"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

for command in modinfo modprobe insmod rmmod sha256sum fuser timeout journalctl rg awk; do
    command -v "$command" >/dev/null || { echo "Falta comando: $command" >&2; exit 1; }
done
[[ "$(uname -r)" == 7.2.9-2-cachyos ]] || { echo "Kernel diferente do build." >&2; exit 1; }
if [[ ! -r "$module" ]]; then
    echo "Módulo ausente ou ilegível: $module" >&2
    echo "O driver não foi descarregado; gere/copie o artefato validado para esse caminho e tente novamente." >&2
    exit 1
fi
module_hash=$(sha256sum "$module" | awk '{print $1}')
module_srcversion=$(modinfo -F srcversion "$module")
echo "module=$module"
echo "module_sha256=$module_hash expected_sha256=$expected_hash"
echo "module_srcversion=$module_srcversion"
if [[ "$module_hash" != "$expected_hash" ]]; then
    echo "Hash divergente: o arquivo existe, mas não é o artefato validado." >&2
    echo "Esperado: $expected_hash" >&2
    echo "Encontrado: $module_hash" >&2
    echo "O driver não foi descarregado; não substitua o módulo carregado." >&2
    exit 1
fi
[[ "$module_srcversion" =~ ^[[:xdigit:]]{24}$ ]] || {
    echo "srcversion ausente ou inválido no artefato." >&2; exit 1;
}
[[ "$(modinfo -F vermagic "$module")" == '7.2.9-2-cachyos SMP preempt mod_unload '* ]] || {
    echo "Vermagic incompatível." >&2; exit 1;
}
[[ -d "$device" && "$(cat "$device/vendor")" == 0x10de &&
   "$(cat "$device/device")" == 0x1140 &&
   "$(cat "$device/subsystem_vendor")" == 0x1028 &&
   "$(cat "$device/subsystem_device")" == 0x05f4 ]] || {
    echo "GPU diferente da GF117 Dell esperada." >&2; exit 1;
}
[[ "$(basename "$(readlink -f "$device/driver")")" == nouveau ]] || {
    echo "O driver ativo precisa ser o Nouveau original." >&2; exit 1;
}
[[ -r /sys/module/nouveau/parameters/noaccel && ! -e "$debugfs/pstate_plan" ]] || {
    echo "Já há um módulo de teste carregado ou o driver não é o esperado; reinicie primeiro." >&2; exit 1;
}
pci_path=$(readlink -f "$device")
for node in /dev/dri/card* /dev/dri/renderD*; do
    [[ -e "$node" ]] || continue
    node_device=$(readlink -f "/sys/class/drm/$(basename "$node")/device" || true)
    if [[ "$node_device" == "$pci_path" ]]; then
        check_gpu_idle "$node" || exit 1
    fi
done
original_noaccel=$(cat /sys/module/nouveau/parameters/noaccel)
original_runpm=$(cat /sys/module/nouveau/parameters/runpm)
original_config=$(cat /sys/module/nouveau/parameters/config)
[[ "$original_config" != '(null)' ]] || original_config=''
run_cursor=$(get_cursor)
[[ -n "$run_cursor" ]] || { echo "Não consegui marcar o início do journal." >&2; exit 1; }
echo "stage=stock-unload"
echo "Removendo somente o módulo Nouveau original."
if timeout --kill-after=2s 15s rmmod nouveau; then
    stock_removed=1
else
    reboot_needed=1; exit 1
fi
check_stock_unload_faults "$run_cursor"
IFS=',' read -r -a dependencies <<< "$(modinfo -F depends "$module")"
for dependency in "${dependencies[@]}"; do
    [[ -z "$dependency" ]] || modprobe "$dependency"
done
load_cursor=$(get_cursor)
echo "stage=experimental-load"
insmod "$module" noaccel=1 runpm=0 config=NvReclockFermiCoreOnly=1
custom_loaded=1
verify_loaded_module_srcversion
[[ -r "$debugfs/pstate_plan" && -r "$debugfs/pstate_current" ]] || {
    echo "Interfaces do módulo de teste ausentes." >&2; exit 1;
}
cat "$debugfs/pstate"
plan=$(cat "$debugfs/pstate_plan")
printf '%s\n' "$plan"
if (( probe_only )); then
    mapfile -t pwm_diag_lines < <(printf '%s\n' "$plan" | rg '^gf117_pwm_diag ' || true)
    mapfile -t plan_state_lines < <(printf '%s\n' "$plan" | rg '^state=[0-9]+ id=' || true)
    [[ ${#plan_state_lines[@]} -gt 0 &&
       ${#pwm_diag_lines[@]} -eq ${#plan_state_lines[@]} ]] || {
        echo "Linha de diagnóstico PWM GF117 ausente." >&2; exit 1;
    }
    for line in "${pwm_diag_lines[@]}"; do
        [[ "$line" =~ ^gf117_pwm_diag\ vbios_vid_pwm_line=(-1|[0-9]+)\ gpio=[[:xdigit:]]{8}\ pwm_index=(-1|0|1|2)\ pwm_enabled=[01]\ selected=[[:xdigit:]]{8}/[[:xdigit:]]{8}\ gpio_lookup=(-?[0-9]+)$ ]] || {
            echo "Formato inesperado na leitura PWM GF117: $line" >&2; exit 1;
        }
    done
    printf 'PWM VBIOS VID_PWM: %s\n' "${pwm_diag_lines[@]}"
    check_faults "$load_cursor"
    echo "Sonda concluída: nenhum pedido de clock foi escrito."
    exit 0
fi
[[ "$plan" == allow_reclock=1* ]] || { echo "Opt-in não foi reconhecido." >&2; exit 1; }
[[ "$plan" == *'requested_core_khz=775000 '* ]] || {
    echo "O estado de 775 MHz esperado não foi encontrado." >&2; exit 1;
}
check_faults "$load_cursor"
check_voltage_plan
read_temperature
sleep 1
read_temperature
read_clocks
(( core > 0 && memory > 0 )) || { echo "GPU sem clocks legíveis." >&2; exit 1; }
memory_before=$memory
check_faults "$load_cursor"
echo "stage=experimental-clock"
echo "Solicitando estado 0f: primeiro pedido de alteração de clock."
clock_attempted=1
printf '0f\n' > "$debugfs/pstate"
wait_target_clock 750 780
for sample in 1 2 3; do
    read_clocks
    (( core >= 750 && core <= 780 && memory == memory_before )) || {
        echo "Clock alvo não confirmado ou memória mudou." >&2; exit 1;
    }
    read_temperature
    check_faults "$load_cursor"
    sleep 1
done
echo "Núcleo >=750 MHz confirmado em repouso; isto NÃO testa estabilidade em jogos."
echo "Retornando ao estado base 07 para encerrar o teste."
printf '07\n' > "$debugfs/pstate"
wait_target_clock 1 300
read_clocks
(( core > 0 && core <= 300 && memory == memory_before )) || {
    echo "Retorno ao estado baixo não confirmado." >&2; exit 1;
}
check_faults "$load_cursor"
clocks_restored=1
echo "Teste breve concluído; o driver original será restaurado."
