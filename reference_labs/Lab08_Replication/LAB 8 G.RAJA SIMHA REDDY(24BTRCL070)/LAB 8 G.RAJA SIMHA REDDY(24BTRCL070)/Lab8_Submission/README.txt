Lab 8 - Replication (MongoDB replica sets with Docker)

BEFORE YOU START
  * Delete any OLD Lab8_Submission folder, then unzip this ZIP into a NEW, empty folder.
  * Start Docker Desktop and wait for "Engine running".
  * pip install -r requirements.txt

HOW TO CHECK YOU HAVE THE RIGHT VERSION
  Open Activity_8.1\docker-compose.yml - it must contain "28017:27017".
  (If it says 27017:27017 you are using an OLD copy.)

RUN (one folder at a time, from inside that folder, in this order)
  cd Activity_8.1                    && python lab_8_1_deploy_replicaset.py
  cd Activity_8.1_Try_It_Yourself    && python lab_8_1_try_it_arbiter.py
  cd Activity_8.2                    && python lab_8_2_failover_observer.py
  cd Activity_8.2_Try_It_Yourself    && python lab_8_2_try_it_priority.py

Each script deploys what it needs (docker compose), runs its .js file with
mongosh INSIDE the container (no local mongosh needed), and prints the results.
The containers are published on localhost ports 28017-28019 (so they never clash
with a MongoDB installed on your PC). Run the folders one after another,
not at the same time.

CLEAN UP
  docker compose -p mongo-rs-lab -f docker-compose.yml down -v
