#!/usr/bin/env bash

set -Eeuo pipefail

deployment_directory="${DEPLOYMENT_DIRECTORY:-/opt/volunteer-crm}"
environment_file="${deployment_directory}/.env.test-deployment"
compose_file="${deployment_directory}/compose.test.yaml"

if [[ ! -f "${environment_file}" ]]; then
  echo "Missing ${environment_file}" >&2
  exit 1
fi

chmod 600 "${environment_file}"
cd "${deployment_directory}"

compose=(docker compose --env-file "${environment_file}" -f "${compose_file}")
"${compose[@]}" config --quiet
"${compose[@]}" up --build -d

demo_container="$("${compose[@]}" ps -aq demo-loader)"
if [[ -z "${demo_container}" ]] || [[ "$(docker inspect --format '{{.State.ExitCode}}' "${demo_container}")" != "0" ]]; then
  "${compose[@]}" logs --tail=200 demo-loader >&2
  echo "The demo-data loader did not complete successfully." >&2
  exit 1
fi

for service in database app fake-oidc frontend; do
  container_id="$("${compose[@]}" ps -q "${service}")"
  if [[ -z "${container_id}" ]]; then
    echo "Service ${service} has no running container." >&2
    exit 1
  fi

  for attempt in {1..36}; do
    health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "${container_id}")"
    [[ "${health}" == "healthy" ]] && break
    [[ "${health}" == "unhealthy" || "${health}" == "exited" || "${health}" == "dead" ]] && break
    sleep 5
  done

  if [[ "${health}" != "healthy" ]]; then
    "${compose[@]}" logs --tail=200 "${service}" >&2
    echo "Service ${service} did not become healthy; final state: ${health}." >&2
    exit 1
  fi
done

gateway_container="$("${compose[@]}" ps -q gateway)"
gateway_state="$(docker inspect --format '{{.State.Status}}' "${gateway_container}")"
if [[ "${gateway_state}" != "running" ]]; then
  "${compose[@]}" logs --tail=200 gateway >&2
  echo "Gateway is not running; final state: ${gateway_state}." >&2
  exit 1
fi

"${compose[@]}" ps
git rev-parse HEAD > .deployed-commit

