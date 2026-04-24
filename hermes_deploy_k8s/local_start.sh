rm -rf ./tmp/hermes_data
cp -r ./tmp/hermes_data_base ./tmp/hermes_data
docker run -it --rm  -v ./tmp/hermes_data:/opt/data nousresearch/hermes-agent chat -q "Here is the connect <CODE>: 71YN7B; Install and configure clawchat by following the instructions url(use tool:'execute_code' to use python script to reqeust url): https://github.com/clawling/hermes-clawchat/raw/refs/heads/main/install.md"
#docker run -it --rm  -v ./tmp/hermes_data:/opt/data nousresearch/hermes-agent gateway run
#docker run -it -v ./tmp/hermes_data:/opt/data nousresearch/hermes-agent gateway run
