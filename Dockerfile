docker build --platform=linux/amd64 -t mysolutionname:somerandomidentifier .


docker run --rm \
  -v "$(pwd)/input:/app/input" \
  -v "$(pwd)/output:/app/output" \
  --network none \
  mysolutionname:somerandomidentifier