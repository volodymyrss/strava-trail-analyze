IMAGE=volodymyrsavchenko/trails:$(shell git describe --always --tags)

build:
	docker build . -t $(IMAGE)

run: build
	docker run -v strava-client.yaml /strava-client.yaml -it -p8000:80 $(IMAGE)

push: build
	docker push $(IMAGE)

listen:
	gunicorn trailsapp:app -b 0.0.0.0:80 --log-level debug

up: push
	helm upgrade --install trails chart --set image.tag=$(shell git describe --always --tags)

cert-manager:
	kubectl apply --validate=false -f https://github.com/jetstack/cert-manager/releases/download/v0.16.1/cert-manager.yaml

