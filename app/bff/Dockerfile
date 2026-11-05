FROM golang:1.26-alpine AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY cmd ./cmd
COPY internal ./internal
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /bff ./cmd/bff

# No shell or package manager. Its numeric user lets Kubernetes verify runAsNonRoot.
FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=build /bff /bff
USER 65532:65532
EXPOSE 8080 9090
ENTRYPOINT ["/bff"]
