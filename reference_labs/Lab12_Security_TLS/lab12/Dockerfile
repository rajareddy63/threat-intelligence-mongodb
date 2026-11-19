FROM mongo:7

ENV DEBIAN_FRONTEND=noninteractive PIP_BREAK_SYSTEM_PACKAGES=1
RUN apt-get update \
 && apt-get install -y --no-install-recommends openssl python3 python3-pip \
 && pip3 install --no-cache-dir pymongo cryptography \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /lab
COPY gen_certs.sh setup.js entrypoint.sh lab12_1_test.py lab12_2_test.py gen_certs.py run_labs.sh ./
RUN chmod +x *.sh

ENV ADMIN_PWD=AdminPass#123 READ_PWD=ReadPass#123 WRITE_PWD=WritePass#123 HR_PWD=HrPass#123

ENTRYPOINT ["/lab/entrypoint.sh"]
CMD ["bash"]
