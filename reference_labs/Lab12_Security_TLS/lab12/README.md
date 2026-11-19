# Chapter 12 Labs - MongoDB Security

Build and run:

    docker build -t lab12-mongo .
    docker run -it --rm lab12-mongo       # starts both mongod instances, drops to bash
    /lab/run_labs.sh                      # full demo of Lab 12.1 + 12.2

- :27017  mongod --auth                       (Lab 12.1)
- :27018  mongod --auth --tlsMode requireTLS  (Lab 12.2)

Users: admin, app_user_read, app_user_write, hr_user (passwords are ENV vars in the Dockerfile).
