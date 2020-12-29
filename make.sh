set -x

function create-secrets() {
	kubectl delete secret strava-client || true
	kubectl create secret generic strava-client  \
		--from-file=strava-client.yaml

	kubectl delete secret flask-secret-key || true
	kubectl create secret generic flask-secret-key  \
                --from-literal=flask-secret-key=$(openssl rand -base64 32)
        
}

$@
