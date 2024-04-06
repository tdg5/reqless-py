#! /usr/bin/env python

import argparse
import logging
import random
import threading
import time

import reqless


# First off, read the arguments
parser = argparse.ArgumentParser(description="Run forgetful workers on contrived jobs.")

parser.add_argument(
    "--forgetfulness",
    dest="forgetfulness",
    default=0.1,
    type=float,
    help="What portion of jobs should be randomly dropped by workers",
)
parser.add_argument(
    "--host",
    dest="host",
    default="localhost",
    help="The host to connect to as the Redis server",
)
parser.add_argument(
    "--port",
    dest="port",
    default=6379,
    type=int,
    help="The port to connect on as the Redis server",
)
parser.add_argument(
    "--stages",
    dest="stages",
    default=1,
    type=int,
    help="How many times to requeue jobs",
)
parser.add_argument(
    "--jobs",
    dest="numJobs",
    default=1000,
    type=int,
    help="How many jobs to schedule for the test",
)
parser.add_argument(
    "--workers",
    dest="numWorkers",
    default=10,
    type=int,
    help="How many workers should do the work",
)
parser.add_argument(
    "--retries",
    dest="retries",
    default=5,
    type=int,
    help="How many retries to give each job",
)
parser.add_argument(
    "--quiet",
    dest="verbose",
    default=True,
    action="store_false",
    help="Reduce all the output",
)
parser.add_argument(
    "--no-flush",
    dest="flush",
    default=True,
    action="store_false",
    help="Don't flush Redis after running",
)

args = parser.parse_args()


logger = logging.getLogger("reqless-bench")
formatter = logging.Formatter("[%(asctime)s] %(threadName)s => %(message)s")
handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
handler.setFormatter(formatter)
logger.addHandler(handler)
if args.verbose:
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.WARN)

# Our reqless client
client = reqless.client(host=args.host, port=args.port)


class ForgetfulWorker(threading.Thread):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        # This is to fake out thread-level workers
        tmp = reqless.client(host=args.host, port=args.port)
        tmp.worker += "-" + self.getName()
        self.q = tmp.queue("testing")

    def run(self):
        while len(self.q):
            job = self.q.pop()
            if not job:
                # Sleep a little bit
                time.sleep(0.1)
                logger.debug("No jobs available. Sleeping.")
                continue
            # Randomly drop a job?
            random_value = random.random()  # noqa: DUO102
            if random_value < args.forgetfulness:
                logger.debug("Randomly dropping job!")
                continue
            else:
                logger.debug("Completing job!")
                job["stages"] -= 1
                if job["stages"] > 0:
                    job.complete("testing")
                else:
                    job.complete()


# Make sure that the redis instance is empty first
if len(client.redis.keys("*")):
    print("Must begin on an empty Redis instance")
    exit(1)

client.config.set("heartbeat", 1)
# This is how much CPU Redis had used /before/
cpu_before = client.redis.info()["used_cpu_user"] + client.redis.info()["used_cpu_sys"]
# This is how long it took to add the jobs
put_time = -time.time()
# Alright, let's make a bunch of jobs
testing = client.queue("testing")
jids = [
    testing.put(
        reqless.Job,
        {"test": "benchmark", "count": c, "stages": args.stages},
        retries=args.retries,
    )
    for c in range(args.numJobs)
]
put_time += time.time()

# This is how long it took to run the workers
work_time = -time.time()
# And now let's make some workers to deal with 'em!
workers = [ForgetfulWorker() for i in range(args.numWorkers)]
for worker in workers:
    worker.start()

for worker in workers:
    worker.join()

work_time += time.time()


def histo(histo_list):
    count = sum(histo_list)
    histo_list_truthy = [bucket for bucket in histo_list if bucket]
    for index in range(len(histo_list_truthy)):
        print(
            "\t\t%2i, %10.9f, %i"
            % (index, float(histo_list_truthy[index]) / count, histo_list_truthy[index])
        )


# Now we'll print out some interesting stats
stats = client.queue("testing").stats()
print("Wait:")
print("\tCount: %i" % stats["wait"]["count"])
print("\tMean : %fs" % stats["wait"]["mean"])
print("\tSDev : %f" % stats["wait"]["std"])
print("\tWait Time Histogram:")
histo(stats["wait"]["histogram"])

print("Run:")
print("\tCount: %i" % stats["run"]["count"])
print("\tMean : %fs" % stats["run"]["mean"])
print("\tSDev : %f" % stats["run"]["std"])
print("\tCompletion Time Histogram:")
histo(stats["run"]["histogram"])

print("=" * 50)
print("Put jobs : %fs" % put_time)
print("Do jobs  : %fs" % work_time)
info = client.redis.info()
print("Redis Mem: %s" % info["used_memory_human"])
print("Redis Lua: %s" % info["used_memory_lua"])
print("Redis CPU: %fs" % (info["used_cpu_user"] + info["used_cpu_sys"] - cpu_before))

# Flush the database when we're done
if args.flush:
    print("Flushing")
    client.redis.flushdb()
