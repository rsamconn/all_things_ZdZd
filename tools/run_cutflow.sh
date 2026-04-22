#!/usr/bin/env bash
# =============================================================================
# run_cutflow.sh
# Automates running the ZdZd cutflow over a list of Ntuple .root files.
#
# Usage:
#   bash run_cutflow.sh [OPTIONS] --input <filepaths.txt>
#
# Required:
#   -i, --input <file>        Path to .txt file containing one Ntuple directory
#                             path per line (blank lines and #-comments ignored)
#
# Optional:
#   -f, --filename <name>     Ntuple filename within each directory
#                             [default: my.output.root]
#   -p, --prefix <prefix>     Prefix for new per-run subdirectory names
#                             [default: (empty)]
#   -g, --goal <string>       Override the goal string written to notes files.
#                             If not set, defaults to per-run auto-generated goal.
#   --setup                   Run ATLAS setup commands before processing
#                             (setupATLAS, asetup --restore, source setup.sh).
#                             By default setup is assumed to already be done.
#   --dry-run                 Resolve all inputs and print all commands that
#                             would be run, then exit without executing anything.
#   -h, --help                Show this help message and exit
#
# Example:
#   bash run_cutflow.sh --input my_ntuples.txt --prefix test --setup
#   bash run_cutflow.sh -i my_ntuples.txt -f custom_output.root --dry-run
# =============================================================================

set -euo pipefail

# =============================================================================
# HARDCODED CONFIGURATION — edit these for your environment
# =============================================================================
readonly SETUP_SH_PATH="/eos/home-c/connell/analyses-ATLAS/analysis-codes/ZdZdPostProcessing_repos/AS_followups_ZdZdPostProcessing/build/x86_64-el9-gcc14-opt/setup.sh"
readonly ATHENA_SCRIPT="ZdZdPlotting/ZdZdPlottingAlgJobOptions.py"
# =============================================================================

# ── Colours for terminal output ───────────────────────────────────────────────
if [[ -t 1 ]]; then
    RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'
    CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'
else
    RED=''; YELLOW=''; GREEN=''; CYAN=''; BOLD=''; RESET=''
fi

# ── Defaults ──────────────────────────────────────────────────────────────────
INPUT_FILE=""
NTUPLE_FILENAME="my.output.root"
DIR_PREFIX=""
GOAL_OVERRIDE=""
RUN_SETUP=false
DRY_RUN=false

# ── Helpers ───────────────────────────────────────────────────────────────────
usage() {
    sed -n '/#.*Usage/,/^# ===/{p}' "$0" | sed 's/^# \{0,3\}//'
    exit 0
}

log_info()    { echo -e "${CYAN}[INFO]${RESET}  $*"; }
log_ok()      { echo -e "${GREEN}[OK]${RESET}    $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
log_error()   { echo -e "${RED}[ERROR]${RESET} $*"; }
log_section() { echo -e "\n${BOLD}$*${RESET}"; }

# ── Argument parsing ──────────────────────────────────────────────────────────
[[ $# -eq 0 ]] && { log_error "No arguments provided."; usage; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        -i|--input)    INPUT_FILE="$2";         shift 2 ;;
        -f|--filename) NTUPLE_FILENAME="$2";    shift 2 ;;
        -p|--prefix)   DIR_PREFIX="$2";         shift 2 ;;
        -g|--goal)     GOAL_OVERRIDE="$2";      shift 2 ;;
        --setup)       RUN_SETUP=true;           shift   ;;
        --dry-run)     DRY_RUN=true;             shift   ;;
        -h|--help)     usage ;;
        *) log_error "Unknown argument: $1"; usage ;;
    esac
done

# ── Validate required arguments ───────────────────────────────────────────────
if [[ -z "$INPUT_FILE" ]]; then
    log_error "--input is required."
    usage
fi

if [[ ! -f "$INPUT_FILE" ]]; then
    log_error "Input file not found: $INPUT_FILE"
    exit 1
fi

# ── Record base directory ─────────────────────────────────────────────────────
BASE_DIR="$(pwd)"
SUMMARY_LOG="${BASE_DIR}/cutflow_summary_$(date +%Y%m%d_%H%M%S).txt"

# =============================================================================
# FUNCTION: parse_ntuple_path
#   Extracts mc_campaign, mZd, and ptag from a directory path.
#   Path must contain a component matching: <campaign>_mZd<mass>[_<ptag>]
#   Sets globals: PARSED_CAMPAIGN, PARSED_MZD, PARSED_PTAG
#   Returns: 0 on full success, 1 if campaign/mZd missing, 2 if ptag missing
# =============================================================================
parse_ntuple_path() {
    local ntuple_path="$1"
    PARSED_CAMPAIGN=""
    PARSED_MZD=""
    PARSED_PTAG=""

    # Extract the last meaningful path component (strip trailing slashes)
    local dir_name
    dir_name="$(basename "${ntuple_path%/}")"

    # Match pattern: <campaign>_mZd<integer>[_<ptag>]
    # campaign = one or more word chars (e.g. mc23a, mc23d)
    # mZd      = integer (e.g. 5, 30, 60)
    # ptag     = optional, matches p followed by digits (e.g. p6491)
    if [[ "$dir_name" =~ ^([a-zA-Z0-9]+)_mZd([0-9]+)(_([pP][0-9]+))?$ ]]; then
        PARSED_CAMPAIGN="${BASH_REMATCH[1]}"
        PARSED_MZD="${BASH_REMATCH[2]}"
        PARSED_PTAG="${BASH_REMATCH[4]}"   # empty string if not present
        if [[ -z "$PARSED_PTAG" ]]; then
            return 2   # campaign + mZd found, but no ptag
        fi
        return 0       # full match
    fi

    # Could not extract campaign or mZd
    return 1
}

# =============================================================================
# FUNCTION: build_run_dir_name
#   Builds the per-run subdirectory name from components and current date.
# =============================================================================
build_run_dir_name() {
    local campaign="$1"
    local mzd="$2"
    local ptag="$3"      # may be empty
    local date_str="$4"  # YYYYMMDD

    local name="${campaign}_mZd${mzd}"
    [[ -n "$ptag" ]] && name+="_${ptag}"
    name+="_${date_str}"
    [[ -n "$DIR_PREFIX" ]] && name="${DIR_PREFIX}_${name}"

    echo "$name"
}

# =============================================================================
# FUNCTION: build_athena_cmd
#   Constructs the full athena command string for a given run.
# =============================================================================
build_athena_cmd() {
    local ntuple_file="$1"   # full path to .root file
    local output_txt="$2"    # path to tee output file

    echo "athena ${ATHENA_SCRIPT} --filesInput=${ntuple_file} --evtMax=-1 | tee ${output_txt}"
}

# =============================================================================
# DRY-RUN MODE
#   Resolve all inputs, print summary, then exit.
# =============================================================================
dry_run_mode() {
    log_section "=== DRY-RUN MODE — no files will be created or commands executed ==="
    echo ""

    local line_num=0
    local run_index=0
    local skip_count=0

    while IFS= read -r line || [[ -n "$line" ]]; do
        (( line_num++ )) || true

        # Skip blank lines and comments
        [[ -z "${line// }" ]]   && continue
        [[ "$line" =~ ^[[:space:]]*# ]] && continue

        local ntuple_dir="${line%/}"   # strip trailing slash
        local date_str
        date_str="$(date +%Y%m%d)"

        (( run_index++ )) || true
        echo -e "${BOLD}── Run #${run_index} (input line ${line_num}) ──────────────────────────${RESET}"
        echo "  Ntuple dir : $ntuple_dir"

        local parse_result
        parse_ntuple_path "$ntuple_dir" || parse_result=$?
        parse_result="${parse_result:-0}"

        if [[ "$parse_result" -eq 1 ]]; then
            log_warn "  Cannot parse MC campaign or mZd from path — WOULD SKIP"
            (( skip_count++ )) || true
            echo ""
            continue
        fi

        if [[ "$parse_result" -eq 2 ]]; then
            log_warn "  p-tag not found in path — would continue without it"
        fi

        local run_dir_name
        run_dir_name="$(build_run_dir_name "$PARSED_CAMPAIGN" "$PARSED_MZD" "$PARSED_PTAG" "$date_str")"
        local run_dir="${BASE_DIR}/${run_dir_name}"

        local ntuple_file="${ntuple_dir}/${NTUPLE_FILENAME}"
        local out_txt="${run_dir}/out_${run_dir_name}.txt"
        local athena_cmd
        athena_cmd="$(build_athena_cmd "$ntuple_file" "$out_txt")"

        local goal="${GOAL_OVERRIDE:-Generating cutflow for ${PARSED_CAMPAIGN}_mZd${PARSED_MZD}${PARSED_PTAG:+_${PARSED_PTAG}}.}"

        echo "  Campaign   : $PARSED_CAMPAIGN"
        echo "  mZd        : $PARSED_MZD GeV"
        echo "  p-tag      : ${PARSED_PTAG:-(not found)}"
        echo "  Run dir    : $run_dir"
        echo "  Input file : $ntuple_file"
        echo "  Output txt : $out_txt"
        echo "  Goal       : $goal"
        echo "  Command    : $athena_cmd"
        echo ""
    done < "$INPUT_FILE"

    local total=$(( run_index ))
    local would_run=$(( run_index - skip_count ))
    echo -e "${BOLD}Summary: ${would_run}/${total} runs would execute, ${skip_count} would be skipped.${RESET}"
    exit 0
}

# =============================================================================
# FUNCTION: run_setup
#   Runs the three ATLAS setup commands from the base directory.
#   Exits the script on any failure.
# =============================================================================
run_setup_commands() {
    log_section "=== Running ATLAS setup commands ==="

    log_info "Running: setupATLAS"
    if ! setupATLAS; then
        log_error "setupATLAS failed. Aborting."
        exit 1
    fi
    log_ok "setupATLAS complete."

    log_info "Running: asetup --restore"
    if ! asetup --restore; then
        log_error "asetup --restore failed. Aborting."
        exit 1
    fi
    log_ok "asetup --restore complete."

    log_info "Running: source ${SETUP_SH_PATH}"
    if ! source "${SETUP_SH_PATH}"; then
        log_error "source ${SETUP_SH_PATH} failed. Aborting."
        exit 1
    fi
    log_ok "ZdZdPostProcessing setup complete."
}

# =============================================================================
# FUNCTION: write_notes
#   Writes the notes file for a completed (or failed) run.
# =============================================================================
write_notes() {
    local notes_file="$1"
    local goal="$2"
    local run_cmd="$3"
    local start_time="$4"
    local end_time="$5"
    local run_dir="$6"
    local exit_code="$7"

    local outcome
    if [[ "$exit_code" -eq 0 ]]; then
        outcome="Success (exit 0)"
    else
        outcome="Failure (exit ${exit_code})"
    fi

    cat > "$notes_file" <<EOF
Goal:       $goal
Command:    $run_cmd
Start time: $start_time
End time:   $end_time
Directory:  $run_dir
Outcome:    $outcome
EOF
}

# =============================================================================
# MAIN EXECUTION
# =============================================================================

# Handle dry-run before setup (setup never runs in dry-run mode)
$DRY_RUN && dry_run_mode

# Run setup if requested
$RUN_SETUP && run_setup_commands

log_section "=== Starting cutflow runs ==="
log_info "Base directory : $BASE_DIR"
log_info "Input file     : $INPUT_FILE"
log_info "Ntuple filename: $NTUPLE_FILENAME"
[[ -n "$DIR_PREFIX" ]] && log_info "Directory prefix: $DIR_PREFIX"
echo ""

# Initialise summary log
{
    echo "Cutflow run summary"
    echo "Generated: $(date)"
    echo "Base dir : $BASE_DIR"
    echo "Input    : $INPUT_FILE"
    echo "========================================"
} > "$SUMMARY_LOG"

# ── Main loop ─────────────────────────────────────────────────────────────────
line_num=0
run_index=0
success_count=0
fail_count=0
skip_count=0

while IFS= read -r line || [[ -n "$line" ]]; do
    (( line_num++ )) || true

    # Skip blank lines and comments
    [[ -z "${line// }" ]]       && continue
    [[ "$line" =~ ^[[:space:]]*# ]] && continue

    ntuple_dir="${line%/}"   # strip trailing slash
    (( run_index++ )) || true

    log_section "── Run #${run_index} ────────────────────────────────────────────"
    log_info "Ntuple dir: $ntuple_dir"

    # ── Parse path ────────────────────────────────────────────────────────────
    parse_result=0
    parse_ntuple_path "$ntuple_dir" || parse_result=$?

    if [[ "$parse_result" -eq 1 ]]; then
        msg="Cannot parse MC campaign or mZd from path — skipping."
        log_warn "$msg"
        echo "SKIPPED  | line ${line_num} | $ntuple_dir | $msg" >> "$SUMMARY_LOG"
        (( skip_count++ )) || true
        continue
    fi

    if [[ "$parse_result" -eq 2 ]]; then
        log_warn "p-tag not found in path — continuing without it."
    fi

    log_info "Campaign : $PARSED_CAMPAIGN"
    log_info "mZd      : $PARSED_MZD GeV"
    log_info "p-tag    : ${PARSED_PTAG:-(not found)}"

    # ── Check Ntuple file exists ──────────────────────────────────────────────
    ntuple_file="${ntuple_dir}/${NTUPLE_FILENAME}"
    if [[ ! -f "$ntuple_file" ]]; then
        msg="Ntuple file not found: ${ntuple_file} — skipping."
        log_warn "$msg"
        echo "SKIPPED  | line ${line_num} | $ntuple_dir | $msg" >> "$SUMMARY_LOG"
        (( skip_count++ )) || true
        continue
    fi

    # ── Build names ───────────────────────────────────────────────────────────
    date_str="$(date +%Y%m%d)"
    run_dir_name="$(build_run_dir_name "$PARSED_CAMPAIGN" "$PARSED_MZD" "$PARSED_PTAG" "$date_str")"
    run_dir="${BASE_DIR}/${run_dir_name}"

    # ── Skip-existing check ───────────────────────────────────────────────────
    if [[ -d "$run_dir" ]]; then
        # Check whether a prior successful run exists
        existing_notes="${run_dir}/notes_${run_dir_name}.txt"
        if [[ -f "$existing_notes" ]] && grep -q "Success" "$existing_notes" 2>/dev/null; then
            msg="Run directory already exists with a successful notes file — skipping: ${run_dir}"
            log_warn "$msg"
            echo "SKIPPED  | line ${line_num} | $ntuple_dir | $msg" >> "$SUMMARY_LOG"
            (( skip_count++ )) || true
            continue
        else
            log_warn "Run directory exists but no prior success detected — proceeding anyway: ${run_dir}"
        fi
    fi

    out_txt="${run_dir}/out_${run_dir_name}.txt"
    notes_file="${run_dir}/notes_${run_dir_name}.txt"
    athena_cmd="$(build_athena_cmd "$ntuple_file" "$out_txt")"
    goal="${GOAL_OVERRIDE:-Generating cutflow for ${PARSED_CAMPAIGN}_mZd${PARSED_MZD}${PARSED_PTAG:+_${PARSED_PTAG}}.}"

    log_info "Run dir  : $run_dir"
    log_info "Command  : $athena_cmd"

    # ── Create run directory ──────────────────────────────────────────────────
    mkdir -p "$run_dir"
    cd "$run_dir"

    # ── Execute athena ────────────────────────────────────────────────────────
    start_time="$(date '+%Y-%m-%d %H:%M:%S')"
    log_info "Starting athena at ${start_time} ..."

    athena_exit=0
    eval "$athena_cmd" || athena_exit=$?

    end_time="$(date '+%Y-%m-%d %H:%M:%S')"

    # ── Write notes file ──────────────────────────────────────────────────────
    write_notes "$notes_file" "$goal" "$athena_cmd" \
                "$start_time" "$end_time" "$run_dir" "$athena_exit"

    # ── Report result ─────────────────────────────────────────────────────────
    if [[ "$athena_exit" -eq 0 ]]; then
        log_ok "Run completed successfully. End time: ${end_time}"
        echo "SUCCESS  | line ${line_num} | ${run_dir_name} | exit 0" >> "$SUMMARY_LOG"
        (( success_count++ )) || true
    else
        log_error "Run FAILED with exit code ${athena_exit}. End time: ${end_time}"
        echo "FAILED   | line ${line_num} | ${run_dir_name} | exit ${athena_exit}" >> "$SUMMARY_LOG"
        (( fail_count++ )) || true
    fi

    # ── Return to base directory ──────────────────────────────────────────────
    cd "$BASE_DIR"

done < "$INPUT_FILE"

# =============================================================================
# FINAL SUMMARY
# =============================================================================
log_section "=== All runs complete ==="
echo -e "  ${GREEN}Succeeded${RESET} : ${success_count}"
echo -e "  ${RED}Failed${RESET}    : ${fail_count}"
echo -e "  ${YELLOW}Skipped${RESET}   : ${skip_count}"
echo -e "  Total     : ${run_index}"
echo ""
log_info "Full summary written to: ${SUMMARY_LOG}"

{
    echo "========================================"
    echo "Succeeded : ${success_count}"
    echo "Failed    : ${fail_count}"
    echo "Skipped   : ${skip_count}"
    echo "Total     : ${run_index}"
} >> "$SUMMARY_LOG"