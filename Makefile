IMAGE=volodymyrsavchenko/trails:$(shell git describe --always --tags)

build:
	docker build . -t $(IMAGE)

run: build
	docker run \
	    --user 1000:1000 \
	    -v $(PWD)/strava-client.yaml:/strava-client.yaml:ro \
	    -e OAUTH_REDIRECT=http://trail.volodymyrsavchenko.com:8000/exchange_token \
	    -it -p8000:8000 $(IMAGE)

push: build
	docker push $(IMAGE)

listen:
	gunicorn trailsapp:app -b 0.0.0.0:8000 --log-level debug

up: push
	helm upgrade --install trails chart --set image.tag=$(shell git describe --always --tags)

cert-manager:
	kubectl apply --validate=false -f https://github.com/jetstack/cert-manager/releases/download/v0.16.1/cert-manager.yaml

