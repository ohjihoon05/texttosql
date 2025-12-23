#!/bin/bash
# wonik4 오프라인 PC 배포 스크립트
#
# 사용법:
#   wonchatgpt에서: ./deploy-wonik4.sh pack   → 압축 파일 생성
#   wonik4에서:     ./deploy-wonik4.sh setup  → 설치 및 실행

set -e

PROJECT_NAME="texttosql"
ARCHIVE_NAME="${PROJECT_NAME}-wonik4.tar.gz"
DEPLOY_PATH="/home/wonik4/Project/oz/${PROJECT_NAME}"

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 1. 패키징 (wonchatgpt PC에서 실행)
pack() {
    log_info "wonik4 배포 패키지 생성 중..."

    # 프로젝트 루트 절대 경로 저장
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
    cd "$SCRIPT_DIR"

    # 임시 디렉토리 생성
    TEMP_DIR=$(mktemp -d)
    PACK_DIR="${TEMP_DIR}/${PROJECT_NAME}"
    mkdir -p "$PACK_DIR"

    log_info "필수 파일 복사 중..."

    # Python 소스 코드 (__pycache__ 제외)
    rsync -a --exclude='__pycache__' --exclude='*.pyc' src "$PACK_DIR/"
    rsync -a --exclude='__pycache__' --exclude='*.pyc' tests "$PACK_DIR/"

    # 설정 파일
    cp requirements.txt "$PACK_DIR/"
    cp pyproject.toml "$PACK_DIR/"
    cp chainlit.md "$PACK_DIR/"
    cp CLAUDE.md "$PACK_DIR/"
    cp .env.wonik4 "$PACK_DIR/"
    cp .env.example "$PACK_DIR/"
    cp .gitignore "$PACK_DIR/"

    # Chainlit 설정
    cp -r .chainlit "$PACK_DIR/"

    # 데이터 디렉토리 (샘플만)
    mkdir -p "$PACK_DIR/data"
    if [ -f "data/sample.xlsx" ]; then
        cp data/sample.xlsx "$PACK_DIR/data/"
    fi

    # 배포 스크립트
    cp deploy-wonik4.sh "$PACK_DIR/"

    # 스펙 문서 (선택)
    if [ -d "specs" ]; then
        cp -r specs "$PACK_DIR/"
    fi

    # .specify 제외 (개발용)
    # .pytest_cache, __pycache__ 제외됨

    # 압축
    log_info "압축 중..."
    cd "$TEMP_DIR"
    tar -czvf "${ARCHIVE_NAME}" "${PROJECT_NAME}"

    # 원래 위치로 복사
    cp "${ARCHIVE_NAME}" "${SCRIPT_DIR}/"
    cd "${SCRIPT_DIR}"

    # 정리
    rm -rf "$TEMP_DIR"

    log_info "✅ 패키지 생성 완료: ${ARCHIVE_NAME}"
    log_info ""
    log_info "wonik4로 복사 후 다음 명령 실행:"
    log_info "  1. tar -xzvf ${ARCHIVE_NAME}"
    log_info "  2. cd ${PROJECT_NAME}"
    log_info "  3. ./deploy-wonik4.sh setup"

    # 파일 크기 표시
    ls -lh "${ARCHIVE_NAME}"
}

# 2. 설치 (wonik4 PC에서 실행)
setup() {
    log_info "wonik4 설치 시작..."

    cd "$(dirname "$0")"

    # Python 가상환경 생성
    if [ ! -d ".venv" ]; then
        log_info "가상환경 생성 중..."
        python3 -m venv .venv
    fi

    # 가상환경 활성화
    source .venv/bin/activate

    # 의존성 설치
    log_info "의존성 설치 중..."
    pip install --upgrade pip
    pip install -r requirements.txt

    # .env 파일 설정
    if [ ! -f ".env" ]; then
        log_info ".env 파일 생성 중..."
        cp .env.wonik4 .env
    else
        log_warn ".env 파일이 이미 존재합니다. 덮어쓰려면 수동으로 복사하세요:"
        log_warn "  cp .env.wonik4 .env"
    fi

    # 데이터 디렉토리 확인
    mkdir -p data

    log_info "✅ 설치 완료!"
    log_info ""
    log_info "실행 방법:"
    log_info "  source .venv/bin/activate"
    log_info "  chainlit run src/main.py --port 3003"
    log_info ""
    log_info "또는:"
    log_info "  ./deploy-wonik4.sh run"
}

# 3. 실행
run() {
    cd "$(dirname "$0")"

    if [ ! -d ".venv" ]; then
        log_error "먼저 setup을 실행하세요: ./deploy-wonik4.sh setup"
        exit 1
    fi

    source .venv/bin/activate

    log_info "서버 시작 (http://localhost:3003)"
    chainlit run src/main.py --port 3003
}

# 4. Ollama 상태 확인
check() {
    log_info "Ollama 상태 확인 중..."

    # Ollama 서버 확인
    if curl -s http://localhost:11435/api/tags > /dev/null 2>&1; then
        log_info "✅ Ollama 서버 정상"
        log_info "설치된 모델:"
        curl -s http://localhost:11435/api/tags | python3 -c "
import sys, json
data = json.load(sys.stdin)
for m in data.get('models', []):
    print(f\"  - {m['name']} ({m.get('size', 'N/A')})\")
" 2>/dev/null || echo "  (모델 목록 파싱 실패)"
    else
        log_error "❌ Ollama 서버에 연결할 수 없습니다"
        log_error "Ollama가 실행 중인지 확인하세요:"
        log_error "  ollama serve"
    fi
}

# 도움말
help() {
    echo "wonik4 오프라인 배포 스크립트"
    echo ""
    echo "사용법: ./deploy-wonik4.sh <command>"
    echo ""
    echo "Commands:"
    echo "  pack   - 배포 패키지 생성 (wonchatgpt PC에서 실행)"
    echo "  setup  - 설치 및 설정 (wonik4 PC에서 실행)"
    echo "  run    - 서버 실행"
    echo "  check  - Ollama 상태 확인"
    echo "  help   - 이 도움말"
}

# 메인
case "${1:-help}" in
    pack)  pack ;;
    setup) setup ;;
    run)   run ;;
    check) check ;;
    *)     help ;;
esac
