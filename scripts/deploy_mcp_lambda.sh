#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${ROOT_DIR}/.build/lambda"
ZIP_PATH="${ROOT_DIR}/.build/mcp_lambda.zip"

LAMBDA_FUNCTION_NAME="${1:-}"
AWS_REGION="${AWS_REGION:-${2:-us-east-2}}"
AWS_PROFILE="${AWS_PROFILE:-alonzo-deploy}"
REQ_FILE="${REQ_FILE:-requirements.lambda.txt}"
LAMBDA_HANDLER="${LAMBDA_HANDLER:-lambda_mcp_handler.lambda_handler}"
PYTHON_BIN="${PYTHON_BIN:-}"
LAMBDA_ROLE_ARN="${LAMBDA_ROLE_ARN:-}"
PIP_PLATFORM="${PIP_PLATFORM:-manylinux2014_x86_64}"

if [[ -z "${LAMBDA_FUNCTION_NAME}" ]]; then
  echo "Usage: $0 <lambda-function-name> [aws-region]"
  echo "Example: $0 game-note-mcp-lambda us-east-2"
  exit 1
fi

if [[ ! -f "${ROOT_DIR}/${REQ_FILE}" ]]; then
  echo "Requirements file not found: ${ROOT_DIR}/${REQ_FILE}"
  exit 1
fi

echo "Packaging Lambda for function: ${LAMBDA_FUNCTION_NAME}"
echo "AWS profile: ${AWS_PROFILE}"
echo "AWS region: ${AWS_REGION}"
echo "Requirements: ${REQ_FILE}"

pick_python() {
  if [[ -n "${PYTHON_BIN}" ]]; then
    echo "${PYTHON_BIN}"
    return 0
  fi

  local candidates=("python3.12" "python3.11" "python3.10" "python3")
  local c
  for c in "${candidates[@]}"; do
    if command -v "${c}" >/dev/null 2>&1; then
      echo "${c}"
      return 0
    fi
  done

  return 1
}

PY="$(pick_python)" || {
  echo "No Python interpreter found. Install Python 3.12+ (recommended) and retry."
  exit 1
}

PY_OK="$("${PY}" -c 'import sys; print(int(sys.version_info >= (3,10)))')"
if [[ "${PY_OK}" != "1" ]]; then
  echo "Python >= 3.10 is required to build this Lambda package (mcp requires it)."
  echo "Detected: $("${PY}" --version)"
  echo "Fix: install Python 3.12 and re-run, or set PYTHON_BIN=/path/to/python3.12"
  exit 1
fi

echo "Build python: $("${PY}" --version)"
echo "Wheel platform: ${PIP_PLATFORM}"

lambda_exists() {
  aws lambda get-function \
    --function-name "${LAMBDA_FUNCTION_NAME}" \
    --region "${AWS_REGION}" \
    --profile "${AWS_PROFILE}" >/dev/null 2>&1
}

rm -rf "${BUILD_DIR}" "${ZIP_PATH}"
mkdir -p "${BUILD_DIR}" "$(dirname "${ZIP_PATH}")"

# Copy project code, excluding heavy/local-only paths.
rsync -a "${ROOT_DIR}/" "${BUILD_DIR}/" \
  --exclude ".git" \
  --exclude ".venv" \
  --exclude "venv" \
  --exclude "__pycache__" \
  --exclude ".pytest_cache" \
  --exclude ".mypy_cache" \
  --exclude ".ruff_cache" \
  --exclude ".build" \
  --exclude "frontend" \
  --exclude "doc" \
  --exclude "scripts/dev" \
  --exclude ".DS_Store"

"${PY}" -m pip install --upgrade pip
"${PY}" -m pip install \
  --platform "${PIP_PLATFORM}" \
  --implementation cp \
  --python-version 3.12 \
  --only-binary=:all: \
  -r "${ROOT_DIR}/${REQ_FILE}" \
  -t "${BUILD_DIR}"

(
  cd "${BUILD_DIR}"
  zip -r "${ZIP_PATH}" . >/dev/null
)

if lambda_exists; then
  aws lambda update-function-code \
    --function-name "${LAMBDA_FUNCTION_NAME}" \
    --zip-file "fileb://${ZIP_PATH}" \
    --region "${AWS_REGION}" \
    --profile "${AWS_PROFILE}" >/dev/null
else
  if [[ -z "${LAMBDA_ROLE_ARN}" ]]; then
    echo "Lambda function does not exist: ${LAMBDA_FUNCTION_NAME}"
    echo "Set LAMBDA_ROLE_ARN to auto-create it, for example:"
    echo "LAMBDA_ROLE_ARN=arn:aws:iam::<account-id>:role/<lambda-exec-role> $0 ${LAMBDA_FUNCTION_NAME} ${AWS_REGION}"
    exit 1
  fi

  echo "Function not found. Creating Lambda: ${LAMBDA_FUNCTION_NAME}"
  aws lambda create-function \
    --function-name "${LAMBDA_FUNCTION_NAME}" \
    --runtime "python3.12" \
    --role "${LAMBDA_ROLE_ARN}" \
    --handler "${LAMBDA_HANDLER}" \
    --zip-file "fileb://${ZIP_PATH}" \
    --timeout 30 \
    --memory-size 512 \
    --region "${AWS_REGION}" \
    --profile "${AWS_PROFILE}" >/dev/null
fi

# Wait until Lambda leaves Pending/Creating before updating config.
aws lambda wait function-active-v2 \
  --function-name "${LAMBDA_FUNCTION_NAME}" \
  --region "${AWS_REGION}" \
  --profile "${AWS_PROFILE}"

# Keep handler in sync with the deployment artifact.
# Retry a few times because Lambda may still be finalizing previous update.
attempt=1
max_attempts=8
while true; do
  if aws lambda update-function-configuration \
    --function-name "${LAMBDA_FUNCTION_NAME}" \
    --handler "${LAMBDA_HANDLER}" \
    --runtime "python3.12" \
    --region "${AWS_REGION}" \
    --profile "${AWS_PROFILE}" >/dev/null 2>&1; then
    break
  fi

  if (( attempt >= max_attempts )); then
    echo "Failed to update function configuration after ${max_attempts} attempts."
    echo "Lambda may still be updating. Retry the deploy command in a minute."
    exit 1
  fi

  echo "Lambda update in progress, retrying configuration update (${attempt}/${max_attempts})..."
  sleep 5
  attempt=$((attempt + 1))
done

echo "Deployment successful."
echo "Lambda: ${LAMBDA_FUNCTION_NAME}"
echo "Handler: ${LAMBDA_HANDLER}"
echo "Artifact: ${ZIP_PATH}"
