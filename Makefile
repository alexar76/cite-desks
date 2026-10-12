.PHONY: help test list up-emberline

help:
	@echo "cite-desks"
	@echo "  make test            kernel pytest"
	@echo "  make list             desks this tree can deploy"
	@echo "  ./deploy.sh <desk>   compose up that desk"

test:
	./deploy.sh --test

list:
	./deploy.sh --list
