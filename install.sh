#!/bin/bash

#===============================================================================
# Memoir AI Memory Framework - Interactive Installation Script
# Only supports Linux
#===============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Configuration
MEMOIR_DIR="$HOME/.memory-chat"
BACKUP_DIR="$HOME/.memory-chat/backups"
VENV_DIR="$HOME/memoir-env"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Default values
DEFAULT_PORT=8000
DEFAULT_LLM_PROVIDER="1"
DEFAULT_LAN_ACCESS="n"
DEFAULT_AUTO_BACKUP="y"

#===============================================================================
# Helper Functions
#===============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo ""
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}========================================${NC}"
}

print_step() {
    echo ""
    echo -e "${BOLD}▶ $1${NC}"
}

ask_choice() {
    local prompt="$1"
    local default="$2"
    local options="$3"

    echo -ne "${BOLD}${prompt}${NC}"
    if [ -n "$default" ]; then
        echo -e " ${CYAN}(默认: $default)${NC}"
    fi
    echo -e "$options"
    echo -n "> "
    read -r choice

    if [ -z "$choice" ]; then
        echo "$default"
    else
        echo "$choice"
    fi
}

ask_input() {
    local prompt="$1"
    local default="$2"
    local is_password="$3"

    echo -ne "${BOLD}${prompt}${NC}"
    if [ -n "$default" ]; then
        echo -ne " ${CYAN}(默认: $default)${NC}"
    fi
    echo -n ": "

    if [ "$is_password" = "y" ]; then
        read -rs choice
    else
        read -r choice
    fi
    echo

    if [ -z "$choice" ]; then
        echo "$default"
    else
        echo "$choice"
    fi
}

check_command() {
    command -v "$1" >/dev/null 2>&1
}

generate_random_hex() {
    head -c 32 /dev/urandom | xxd -p | tr -d '\n'
}

generate_user_id() {
    head -c 8 /dev/urandom | xxd -p | tr -d '\n' | cut -c1-8
}

find_available_port() {
    local port=$1
    while :; do
        if ! lsof -i:$port >/dev/null 2>&1; then
            echo $port
            return 0
        fi
        port=$((port + 1))
        if [ $port -gt 65535 ]; then
            return 1
        fi
    done
}

test_url() {
    local url="$1"
    local timeout="${2:-5}"

    if curl -s --max-time "$timeout" "$url" >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

#===============================================================================
# Welcome
#===============================================================================

print_header "Memoir AI 长期记忆框架"

echo -e "
${BOLD}欢迎使用 Memoir 安装脚本！${NC}

Memoir 是一个轻量级的 AI 长期记忆框架，让 AI 助手具备\"记忆\"能力。

本脚本将自动完成以下工作：
  • 环境检查
  • 依赖安装
  • LLM 提供商配置
  • 安全设置
  • 服务启动

${YELLOW}注意：此脚本仅支持 Linux 系统${NC}
"

read -p "按回车键继续..." </dev/null

#===============================================================================
# Environment Check
#===============================================================================

print_step "1/7 环境检查"

# Check if running as root (not recommended)
if [ "$(id -u)" -eq 0 ]; then
    log_warn "建议不要使用 root 用户运行此脚本"
    read -p "继续安装? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 0
    fi
fi

# Check Python version
if ! check_command python3; then
    log_error "Python 3 未安装"
    echo "请先安装 Python 3.9+："
    echo "  Ubuntu/Debian: sudo apt update && sudo apt install python3 python3-pip python3-venv"
    echo "  CentOS/RHEL:   sudo yum install python3 python3-pip"
    echo "  Arch Linux:    sudo pacman -S python python-pip python-venv"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
PYTHON_MAJOR=$(python3 -c 'import sys; print(sys.version_info[0])')
PYTHON_MINOR=$(python3 -c 'import sys; print(sys.version_info[1])')

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 9 ]); then
    log_error "Python 版本过低: $PYTHON_VERSION，需要 3.9+"
    exit 1
fi

log_success "Python 版本: $PYTHON_VERSION"

# Check pip
if ! check_command pip3 && ! check_command pip; then
    log_error "pip 未安装"
    echo "请先安装 pip："
    echo "  curl -sS https://bootstrap.pypa.io/get-pip.py | python3"
    exit 1
fi

log_success "pip 已安装"

# Check venv
if ! python3 -c "import venv" 2>/dev/null; then
    log_warn "python3-venv 未安装，正在尝试安装..."
    if check_command apt-get; then
        sudo apt-get update && sudo apt-get install -y python3-venv
    elif check_command yum; then
        sudo yum install -y python3-venv
    elif check_command pacman; then
        sudo pacman -S python-venv
    fi

    if ! python3 -c "import venv" 2>/dev/null; then
        log_error "无法安装 python3-venv，请手动安装后重试"
        exit 1
    fi
fi

log_success "python3-venv 已安装"

# Check project directory
if [ ! -d "$PROJECT_DIR/src" ] || [ ! -f "$PROJECT_DIR/pyproject.toml" ]; then
    log_error "项目目录不正确: $PROJECT_DIR"
    echo "请在 Memoir 项目根目录运行此脚本"
    exit 1
fi

log_success "项目目录: $PROJECT_DIR"

#===============================================================================
# LLM Provider Configuration
#===============================================================================

print_step "2/7 LLM 提供商配置"

LLM_PROVIDER=$(ask_choice "请选择 LLM 提供商" "$DEFAULT_LLM_PROVIDER" "
  1) Ollama (本地模型)
  2) OpenAI / 兼容服务 (如 DeepSeek、硅基流动)")

# LLM settings
if [ "$LLM_PROVIDER" = "1" ]; then
    # Ollama
    LLM_PROVIDER_NAME="ollama"
    LLM_BASE_URL=$(ask_input "Ollama 服务地址" "http://localhost:11434")

    # Test connection
    print_step "测试 Ollama 连接..."
    if test_url "$LLM_BASE_URL/api/tags" 5; then
        log_success "Ollama 服务连接成功"

        # Optional: Pull recommended model
        echo ""
        read -p "是否自动拉取推荐模型 qwen2.5:7b? [Y/n] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]] || [ -z "$REPLY" ]; then
            log_info "正在后台拉取模型 qwen2.5:7b ..."
            nohup ollama pull qwen2.5:7b >/dev/null 2>&1 &
            log_info "模型将在后台拉取，您可以在 Web UI 中查看进度"
        fi
    else
        log_error "无法连接到 Ollama 服务: $LLM_BASE_URL"
        echo "请确保 Ollama 已启动: ollama serve"
        exit 1
    fi

    LLM_MODEL=$(ask_input "请输入模型名称" "qwen2.5:7b")
else
    # OpenAI compatible
    LLM_PROVIDER_NAME="openai"

    echo ""
    LLM_API_KEY=$(ask_input "请输入 API Key" "" "y")

    if [ -z "$LLM_API_KEY" ]; then
        log_error "API Key 不能为空"
        exit 1
    fi

    LLM_BASE_URL=$(ask_input "请输入 Base URL" "https://api.openai.com/v1")
    LLM_MODEL=$(ask_input "请输入默认模型" "gpt-3.5-turbo")

    # Optional: Test connection
    echo ""
    read -p "是否测试 API 连接? [Y/n] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]] || [ -z "$REPLY" ]; then
        log_info "正在测试 API 连接..."

        # Test with a minimal request
        TEST_RESPONSE=$(curl -s -w "%{http_code}" -o /dev/null \
            -H "Authorization: Bearer $LLM_API_KEY" \
            -H "Content-Type: application/json" \
            "$LLM_BASE_URL/models" 2>/dev/null || echo "000")

        if [ "$TEST_RESPONSE" = "200" ]; then
            log_success "API 连接测试成功"
        else
            log_warn "API 连接测试失败 (HTTP $TEST_RESPONSE)，但您可以继续安装"
        fi
    fi
fi

#===============================================================================
# Security Settings
#===============================================================================

print_step "3/7 安全设置"

LAN_ACCESS=$(ask_choice "是否允许局域网访问?" "$DEFAULT_LAN_ACCESS" "
  y) 是，允许局域网其他设备访问
  n) 否，仅本地 127.0.0.1")

if [ "$LAN_ACCESS" = "y" ]; then
    SERVER_HOST="0.0.0.0"
    log_info "将监听所有网络接口"
else
    SERVER_HOST="127.0.0.1"
    log_info "仅监听本地地址"
fi

# Port
echo ""
log_info "检测端口 ${DEFAULT_PORT} ..."
SERVER_PORT=$(find_available_port $DEFAULT_PORT)
if [ "$SERVER_PORT" != "$DEFAULT_PORT" ]; then
    log_warn "端口 $DEFAULT_PORT 已被占用，使用端口 $SERVER_PORT"
else
    log_success "端口 $SERVER_PORT 可用"
fi

# Generate API Key
API_KEY="sk_$(generate_random_hex)"
log_success "API Key 已生成"

# Generate User ID
USER_ID="user_$(generate_user_id)"
log_success "用户 ID: $USER_ID"

#===============================================================================
# Data Directory
#===============================================================================

print_step "4/7 数据目录"

# Create directories
mkdir -p "$MEMOIR_DIR/meta"
mkdir -p "$BACKUP_DIR"

log_success "数据目录: $MEMOIR_DIR"
log_success "备份目录: $BACKUP_DIR"

# Record install time
echo "Install time: $(date -Iseconds)" > "$MEMOIR_DIR/meta/install.log"

#===============================================================================
# Auto Backup (Optional)
#===============================================================================

print_step "5/7 定时备份"

AUTO_BACKUP=$(ask_choice "是否启用自动备份?" "$DEFAULT_AUTO_BACKUP" "
  y) 是，每周备份一次，保留最近 3 份
  n) 否，跳过备份配置")

BACKUP_ENABLED="false"
BACKUP_CRON=""

if [ "$AUTO_BACKUP" = "y" ]; then
    BACKUP_ENABLED="true"
    BACKUP_CRON="0 2 * * 0"  # Every Sunday at 2 AM

    # Create backup script
    cat > "$MEMOIR_DIR/backup.sh" << 'BACKUP_EOF'
#!/bin/bash
#===============================================================================
# Memoir Auto Backup Script
#===============================================================================

BACKUP_DIR="$HOME/.memory-chat/backups"
DATA_DIR="$HOME/.memory-chat"
KEEP=3

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Generate backup filename
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/memoir_backup_${TIMESTAMP}.tar.gz"

# Create backup (exclude logs and cache)
tar -czf "$BACKUP_FILE" \
    --exclude='*.log' \
    --exclude='__pycache__' \
    --exclude='.cache' \
    -C "$HOME" .memory-chat 2>/dev/null

# Clean old backups
cd "$BACKUP_DIR" || exit 1
ls -t memoir_backup_*.tar.gz 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm -f

echo "Backup created: $BACKUP_FILE"
echo "Backup size: $(du -h "$BACKUP_FILE" | cut -f1)"
BACKUP_EOF

    chmod +x "$MEMOIR_DIR/backup.sh"
    log_success "备份脚本已创建: $MEMOIR_DIR/backup.sh"

    # Add to crontab
    CRON_JOB="0 2 * * 0 $MEMOIR_DIR/backup.sh >> $MEMOIR_DIR/meta/backup.log 2>&1"

    # Backup existing crontab
    crontab -l > "$MEMOIR_DIR/meta/crontab.bak" 2>/dev/null || true

    # Add new job
    (crontab -l 2>/dev/null | grep -v "memoir_backup.sh"; echo "$CRON_JOB") | crontab -

    log_success "已添加到 crontab: 每周日凌晨 2 点自动备份"
else
    log_info "跳过自动备份配置"
fi

#===============================================================================
# Install Dependencies
#===============================================================================

print_step "6/7 安装依赖"

# Create virtual environment
log_info "创建虚拟环境: $VENV_DIR"
python3 -m venv "$VENV_DIR"

# Activate venv and install
log_info "安装 Python 依赖..."
source "$VENV_DIR/bin/activate"
pip install --upgrade pip >/dev/null 2>&1
pip install -e "$PROJECT_DIR" >/dev/null 2>&1
deactivate

log_success "依赖安装完成"

#===============================================================================
# Generate Configuration
#===============================================================================

print_step "生成配置文件"

cat > "$MEMOIR_DIR/config.yaml" << CONFIG_EOF
# Memoir Configuration
# Generated by install.sh on $(date +%Y-%m-%d)

server:
  host: "$SERVER_HOST"
  port: $SERVER_PORT

auth:
  enabled: true
  api_key: "$API_KEY"

storage:
  base_dir: "$MEMOIR_DIR"
  users_dir: "users"

memory:
  short_term_max_messages: 1000
  long_term_chunk_size: 2000

index:
  vector:
    enabled: true
  fulltext:
    enabled: true

llm:
  provider: "$LLM_PROVIDER_NAME"
  model: "$LLM_MODEL"
  base_url: "$LLM_BASE_URL"
  ${LLM_PROVIDER_NAME}:
    api_key: "$LLM_API_KEY"
    model: "$LLM_MODEL"
    base_url: "$LLM_BASE_URL"

retrieval:
  top_k: 5
  similarity_threshold: 0.7
  expand_session_turns: 3
  expand_time_days: 7

backup:
  enabled: $BACKUP_ENABLED
  cron: "$BACKUP_CRON"
  keep: 3
  path: "$BACKUP_DIR"

logging:
  level: "INFO"
CONFIG_EOF

# Set file permissions
chmod 600 "$MEMOIR_DIR/config.yaml"
log_success "配置文件已生成: $MEMOIR_DIR/config.yaml"

# Create symlink to project config
ln -sf "$MEMOIR_DIR/config.yaml" "$PROJECT_DIR/config.yaml"

#===============================================================================
# Start Service
#===============================================================================

print_step "7/7 启动服务"

# Create startup script
cat > "$PROJECT_DIR/memoir.sh" << MEMOIR_SH_EOF
#!/bin/bash
#===============================================================================
# Memoir Management Script
#===============================================================================

PROJECT_DIR="$(cd "\$(dirname "\${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$HOME/memoir-env"
CONFIG_DIR="$HOME/.memory-chat"
PID_FILE="$CONFIG_DIR/memoir.pid"
LOG_FILE="$CONFIG_DIR/meta/memoir.log"

source "$VENV_DIR/bin/activate"

case "\$1" in
    start)
        if [ -f "$PID_FILE" ]; then
            PID=\$(cat "$PID_FILE")
            if ps -p \$PID > /dev/null 2>&1; then
                echo "Memoir 已在运行 (PID: \$PID)"
                exit 0
            fi
        fi
        echo "启动 Memoir 服务..."
        cd "$PROJECT_DIR"
        uvicorn src.main:app --host "$SERVER_HOST" --port $SERVER_PORT > "$LOG_FILE" 2>&1 &
        echo \$! > "$PID_FILE"
        sleep 3

        # Check if running
        if curl -s http://$SERVER_HOST:$SERVER_PORT/health >/dev/null 2>&1; then
            echo "Memoir 已启动 (PID: \$(cat $PID_FILE))"
        else
            echo "启动失败，请查看日志: $LOG_FILE"
            rm -f "$PID_FILE"
            exit 1
        fi
        ;;
    stop)
        if [ -f "$PID_FILE" ]; then
            PID=\$(cat "$PID_FILE")
            if ps -p \$PID > /dev/null 2>&1; then
                kill \$PID
                rm -f "$PID_FILE"
                echo "Memoir 已停止"
            else
                rm -f "$PID_FILE"
                echo "Memoir 未在运行"
            fi
        else
            echo "Memoir 未在运行"
        fi
        ;;
    restart)
        \$0 stop
        sleep 2
        \$0 start
        ;;
    status)
        if [ -f "$PID_FILE" ]; then
            PID=\$(cat "$PID_FILE")
            if ps -p \$PID > /dev/null 2>&1; then
                echo "Memoir 正在运行 (PID: \$PID)"
                exit 0
            fi
        fi
        echo "Memoir 未在运行"
        exit 1
        ;;
    log)
        tail -f "$LOG_FILE"
        ;;
    *)
        echo "用法: $0 {start|stop|restart|status|log}"
        exit 1
        ;;
esac
MEMOIR_SH_EOF

chmod +x "$PROJECT_DIR/memoir.sh"
log_success "管理脚本已创建: $PROJECT_DIR/memoir.sh"

# Start service
cd "$PROJECT_DIR"
source "$VENV_DIR/bin/activate"

nohup uvicorn src.main:app --host "$SERVER_HOST" --port $SERVER_PORT > "$MEMOIR_DIR/meta/memoir.log" 2>&1 &
SERVICE_PID=$!
echo "$SERVICE_PID" > "$MEMOIR_DIR/meta/memoir.pid"

# Wait and check health
sleep 3

if curl -s "http://${SERVER_HOST}:${SERVER_PORT}/health" >/dev/null 2>&1; then
    log_success "Memoir 服务启动成功"
else
    log_error "服务启动失败，请查看日志: $MEMOIR_DIR/meta/memoir.log"
    exit 1
fi

deactivate

#===============================================================================
# Output Results
#===============================================================================

print_header "安装完成!"

echo -e "
${GREEN}═══════════════════════════════════════════════════════════════${NC}

${BOLD}访问地址:${NC}
  ${CYAN}http://${SERVER_HOST}:${SERVER_PORT}${NC}

${BOLD}API Key:${NC}
  ${YELLOW}$API_KEY${NC}
  ${RED}⚠ 请妥善保存，这是访问服务的唯一凭证！${NC}

${BOLD}用户 ID:${NC}
  $USER_ID

${BOLD}数据目录:${NC}
  $MEMOIR_DIR

${GREEN}═══════════════════════════════════════════════════════════════${NC}

${BOLD}管理命令:${NC}
  $PROJECT_DIR/memoir.sh start   # 启动服务
  $PROJECT_DIR/memoir.sh stop    # 停止服务
  $PROJECT_DIR/memoir.sh restart # 重启服务
  $PROJECT_DIR/memoir.sh status  # 查看状态
  $PROJECT_DIR/memoir.sh log     # 查看日志

${BOLD}首次使用:${NC}
  1. 在浏览器打开 http://${SERVER_HOST}:${SERVER_PORT}
  2. 在 Web UI 中使用\"导入对话\"功能快速构建记忆
  3. 开始与 AI 助手对话！

${GREEN}═══════════════════════════════════════════════════════════════${NC}
"

log_success "祝您使用愉快！"
