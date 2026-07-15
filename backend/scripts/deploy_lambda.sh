#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 4 ]]; then
  echo "Usage: $0 <source-file> <function-name> <build-name> <requirements-file>" >&2
  exit 1
fi

SOURCE_FILE="$1"
FUNCTION_NAME="$2"
BUILD_NAME="$3"
REQUIREMENTS_FILE="$4"

if [[ -z "${FUNCTION_NAME}" ]]; then
  echo "Function name must not be empty." >&2
  exit 1
fi

if [[ ! "${BUILD_NAME}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
  echo "Build name must start with an alphanumeric character and contain only letters, numbers, dots, underscores, or hyphens." >&2
  exit 1
fi

for command_name in python zip unzip aws; do
  if ! command -v "${command_name}" >/dev/null 2>&1; then
    echo "Required command not found: ${command_name}" >&2
    exit 1
  fi
done

BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${BACKEND_DIR}"

if [[ ! -f "${SOURCE_FILE}" ]]; then
  echo "Source file not found: ${SOURCE_FILE}" >&2
  exit 1
fi

if [[ ! -f "${REQUIREMENTS_FILE}" ]]; then
  echo "Requirements file not found: ${REQUIREMENTS_FILE}" >&2
  exit 1
fi

BUILD_DIR="${BACKEND_DIR}/build/${BUILD_NAME}"
ZIP_FILE="${BACKEND_DIR}/build/${BUILD_NAME}.zip"
EXPECTED_HANDLER="lambda_function.lambda_handler"
EXPECTED_RUNTIME="python3.13"
EXPECTED_ARCHITECTURE="x86_64"
MAX_ZIP_SIZE_BYTES=$((50 * 1024 * 1024))

cleanup() {
  rm -rf -- "${BUILD_DIR}" "${ZIP_FILE}"
  rmdir "${BACKEND_DIR}/build" 2>/dev/null || true
}

remove_package_artifacts() {
  find "${BUILD_DIR}" -type d \( -name __pycache__ -o -name test -o -name tests \) \
    -prune -exec rm -rf -- {} +
  find "${BUILD_DIR}" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete
}

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

cleanup
mkdir -p "${BUILD_DIR}"

aws lambda wait function-updated \
  --function-name "${FUNCTION_NAME}"

read -r handler runtime architecture < <(
  aws lambda get-function-configuration \
    --function-name "${FUNCTION_NAME}" \
    --query '[Handler,Runtime,Architectures[0]]' \
    --output text
)

if [[ "${handler}" != "${EXPECTED_HANDLER}" ]]; then
  echo "Unexpected handler for ${FUNCTION_NAME}: ${handler} (expected ${EXPECTED_HANDLER})" >&2
  exit 1
fi

if [[ "${runtime}" != "${EXPECTED_RUNTIME}" ]]; then
  echo "Unexpected runtime for ${FUNCTION_NAME}: ${runtime} (expected ${EXPECTED_RUNTIME})" >&2
  exit 1
fi

if [[ "${architecture}" != "${EXPECTED_ARCHITECTURE}" ]]; then
  echo "Unexpected architecture for ${FUNCTION_NAME}: ${architecture} (expected ${EXPECTED_ARCHITECTURE})" >&2
  exit 1
fi

python -m pip install \
  --disable-pip-version-check \
  --no-compile \
  --require-hashes \
  --platform manylinux2014_x86_64 \
  --implementation cp \
  --python-version 3.13 \
  --only-binary=:all: \
  --target "${BUILD_DIR}" \
  -r "${REQUIREMENTS_FILE}"

cp "${SOURCE_FILE}" "${BUILD_DIR}/lambda_function.py"

remove_package_artifacts

PYTHONPATH="${BUILD_DIR}" \
PYTHONDONTWRITEBYTECODE=1 \
VIDWIZ_ENDPOINT="https://example.invalid" \
VIDWIZ_TOKEN="deployment-smoke-test" \
SQS_QUEUE_URL="https://example.invalid/note-queue" \
SQS_SUMMARY_QUEUE_URL="https://example.invalid/summary-queue" \
S3_BUCKET_NAME="deployment-smoke-test" \
OPENROUTER_API_KEY="deployment-smoke-test" \
python - <<'PY'
import importlib

for dependency in ("aws_lambda_powertools", "boto3", "requests"):
    importlib.import_module(dependency)

handler_module = importlib.import_module("lambda_function")
if not callable(getattr(handler_module, "lambda_handler", None)):
    raise RuntimeError("lambda_function.lambda_handler is missing or not callable")
PY

remove_package_artifacts

(
  cd "${BUILD_DIR}"
  zip -q -r "${ZIP_FILE}" .
)

unzip -tq "${ZIP_FILE}" >/dev/null

if ! unzip -Z1 "${ZIP_FILE}" | grep -qx 'lambda_function.py'; then
  echo "Archive does not contain root-level lambda_function.py" >&2
  exit 1
fi

if unzip -Z1 "${ZIP_FILE}" | grep -Eq '(^|/)(__pycache__|tests?)/|\.(pyc|pyo)$'; then
  echo "Archive contains excluded bytecode or test artifacts" >&2
  exit 1
fi

zip_size_bytes="$(wc -c < "${ZIP_FILE}")"
if (( zip_size_bytes > MAX_ZIP_SIZE_BYTES )); then
  echo "Archive is ${zip_size_bytes} bytes; direct Lambda uploads are limited to ${MAX_ZIP_SIZE_BYTES} bytes" >&2
  exit 1
fi

echo "Updating ${FUNCTION_NAME}..."
aws lambda update-function-code \
  --function-name "${FUNCTION_NAME}" \
  --zip-file "fileb://${ZIP_FILE}" \
  --no-cli-pager >/dev/null

aws lambda wait function-updated \
  --function-name "${FUNCTION_NAME}"

echo "Deployed ${FUNCTION_NAME}"
