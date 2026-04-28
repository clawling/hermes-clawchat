JWT="Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzaWQiOjI4LCJkaWQiOiJvcGVuY2xhdy1jbGF3Y2hhdCIsImFpZCI6ImFndF8wMUtQTjZTUUZRRUdKOThDSFYwNkdGMk5aWiIsIm9pZCI6InVzcl8wMUtQQTVOSzYyRTk0UkJBTVQyM1dRU0dWNCIsInN1YiI6InVzcl8wMUtQTjZTUUZRRUdNOUhSMTFDSFJIUE1NVCIsImV4cCI6MTc3OTI3Mjc1OCwiaWF0IjoxNzc2NjgwNzU4fQ.cAu3vJcZFxzsaMLouq_8eIL41cLzD9xt2rmGlVvy-HE2QCPytjNbBBqEgcn39WQHwemV1QlPPfTfiiJfoW3OsCoLcZ0vGkZZFxaMnzbzD3qq1KZ9WpGv--_m8V4F3XLmLWn0X9XlB_bTOMVAhBNbO9qKPzOxu5MQJLMsCjaNypwhVoLIOHjVgzzHLL-NjusP2_pWn8eW3otR125wd8gyTNPewxM2rsZliw0yq_pIDDv2wupC1Pgtv7qfWtxjWsbx8-Sa4OsUYBC3OKGZKoE5-M98XZTGqr1u65q8qvz9rUU0l_lZWHfYlioKgAAABUFzlFtMI2SFd9S86C_eWY1FKQ"

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
