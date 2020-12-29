set -x

function create-secrets() {
	kubectl delete secret strava-client || true
	kubectl create secret generic strava-client  \
		--from-file=strava-client.yaml
}

$@
