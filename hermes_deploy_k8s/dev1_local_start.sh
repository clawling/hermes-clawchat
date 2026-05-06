JWT="Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzaWQiOjIzMSwiZGlkIjoiLCBhcGlmb3giLCJzdWIiOiJ1c3JfMDFLUEE1Tks2MkU5NFJCQU1UMjNXUVNHVjQiLCJleHAiOjE3ODA2MjY2ODksImlhdCI6MTc3ODAzNDY4OX0.eYRQr1_p1aBMC4J3pkbeB-roIMGWu8RujNaX9Ian9d3o8f6ra2T_p_h6OnG3P0zAPYm69OddsvctoZxiirI8N5BfLY_oSSK8DQ8vAT_qR5uPStLv1keMLNLZWIrUvMidZObnQ_6ehGzYvIRdrGc79KSbB7uzBwonPSL0C_kinFdH3UzPBb1e6gMKrD_PP6TbRZ4ABGEbo95NMPSwmktoV5eomOZCIGmWNHvmgFvkkFnLyZ-YEs2JRc719N3DUNxet4_QTPgtMJyd3yGsbYQ47A9kJZ5Yq7DNySgGwD-HFPyq4eVbdSI3yol4DRKk3sChSlwzFf0XMpDcDf8dwAl_OA"

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
docker run -it --rm -v ./tmp/hermes_data:/opt/data nousresearch/hermes-agent chat -q "Here is the connect <CODE>: $CODE; Install and configure clawchat by following the instructions url(use tool:'execute_code' to use python script to reqeust url): https://raw.githubusercontent.com/clawling/hermes-clawchat/refs/heads/joe/test/install.md"
#docker run -it --rm  -v ./tmp/hermes_data:/opt/data nousresearch/hermes-agent gateway run
#docker run -it -v ./tmp/hermes_data:/opt/data nousresearch/hermes-agent gateway run
