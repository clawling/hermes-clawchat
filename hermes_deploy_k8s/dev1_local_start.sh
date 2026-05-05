JWT="Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzaWQiOjIyOCwiZGlkIjoiLCBhcGlmb3giLCJzdWIiOiJ1c3JfMDFLUEE1Tks2MkU5NFJCQU1UMjNXUVNHVjQiLCJleHAiOjE3ODA1NzcyMDksImlhdCI6MTc3Nzk4NTIwOX0.ZqwbXr7kMgC37TYQDBrhiYnYeWwHzPgnDJT8SAl8MsTYTXSAQcEBwqt4QuHOeq5MEoQB2-UjzqcVtBmhpRoX_vW81nIzOi8RXphTjaeoEkohm9eD_xHirY6rXwQM75o_2laFkmPBmcB3TNSE8oSXjOHKPOnR-ogvpf9c1FzK2UYx8elkB17auzyzsNmZaPluYlDaF5hzbDKL3H7yqkrtB85YL73EJ9YPPUfBBP5Z52YHWWAJLmMlCal2qNYNMv6OoWjGZFBqWrygCfA1XEd6twLFDXTjZst-lObs7mcsqrAjM4dnjWOsGy4B08vWzF9oBJjHkmPELO4GYGLiJgm4rQ"

RESPONSE=$(curl -sS --location --request POST 'http://company.newbaselab.com:19001/v1/agents/connect-codes' \
    --header 'x-device-id: apifox' \
    --header "Authorization: $JWT")

echo "connect-codes response: $RESPONSE"

CODE=$(echo "$RESPONSE" | python3 -c "import sys, json; d = json.load(sys.stdin); print(d.get('data', {}).get('code') or d.get('code', ''))")

if [ -z "$CODE" ]; then
    echo "failed to obtain connect code" >&2
    exit 1
fi

echo "connect code: $CODE"

rm -rf ./tmp/hermes_data
cp -r ./tmp/hermes_data_base ./tmp/hermes_data
docker run -it --restart=unless-stopped  -v ./tmp/hermes_data:/opt/data nousresearch/hermes-agent chat -q "Here is the connect <CODE>: $CODE; Install and configure clawchat by following the instructions url(use tool:'execute_code' to use python script to reqeust url): https://raw.githubusercontent.com/clawling/hermes-clawchat/refs/heads/joe/test/install.md"
#docker run -it --rm  -v ./tmp/hermes_data:/opt/data nousresearch/hermes-agent gateway run
#docker run -it -v ./tmp/hermes_data:/opt/data nousresearch/hermes-agent gateway run
