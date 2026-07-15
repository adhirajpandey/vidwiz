#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "Usage: $0 <source-file> <function-name> <build-name>" >&2
  exit 1
fi

SOURCE_FILE="$1"
FUNCTION_NAME="$2"
BUILD_NAME="$3"

if [[ -z "${FUNCTION_NAME}" ]]; then
  echo "Function name must not be empty." >&2
  exit 1
fi

if [[ ! "${BUILD_NAME}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
  echo "Build name must start with an alphanumeric character and contain only letters, numbers, dots, underscores, or hyphens." >&2
  exit 1
fi

for command_name in zip aws; do
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

BUILD_DIR="${BACKEND_DIR}/build/${BUILD_NAME}"
ZIP_FILE="${BACKEND_DIR}/build/${BUILD_NAME}.zip"

cleanup() {
  rm -rf -- "${BUILD_DIR}" "${ZIP_FILE}"
  rmdir "${BACKEND_DIR}/build" 2>/dev/null || true
}

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

cleanup
mkdir -p "${BUILD_DIR}"
cp "${SOURCE_FILE}" "${BUILD_DIR}/lambda_function.py"

(
  cd "${BUILD_DIR}"
  zip -q -r "${ZIP_FILE}" .
)

echo "Updating ${FUNCTION_NAME}..."
aws lambda update-function-code \
  --function-name "${FUNCTION_NAME}" \
  --zip-file "fileb://${ZIP_FILE}" \
  --no-cli-pager >/dev/null

aws lambda wait function-updated \
  --function-name "${FUNCTION_NAME}"

echo "Deployed ${FUNCTION_NAME}"
