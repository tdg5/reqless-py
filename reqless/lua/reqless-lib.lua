-- Current SHA: 4504ab481b84f03fcfd10318bf18c5835b31d159
-- This is a generated file
-------------------------------------------------------------------------------
-- Forward declarations to make everything happy
-------------------------------------------------------------------------------
local Reqless = {
  ns = 'ql:'
}

-- Queue forward delcaration
local ReqlessQueue = {
  ns = Reqless.ns .. 'q:'
}
ReqlessQueue.__index = ReqlessQueue

-- Worker forward declaration
local ReqlessWorker = {
  ns = Reqless.ns .. 'w:'
}
ReqlessWorker.__index = ReqlessWorker

-- Job forward declaration
local ReqlessJob = {
  ns = Reqless.ns .. 'j:'
}
ReqlessJob.__index = ReqlessJob

-- throttle forward declaration
local ReqlessThrottle = {
  ns = Reqless.ns .. 'th:'
}
ReqlessThrottle.__index = ReqlessThrottle

-- RecurringJob forward declaration
local ReqlessRecurringJob = {}
ReqlessRecurringJob.__index = ReqlessRecurringJob

-- Config forward declaration
Reqless.config = {}

-- Extend a table. This comes up quite frequently
local function table_extend(self, other)
  for _, v in ipairs(other) do
    table.insert(self, v)
  end
end

-- This is essentially the same as redis' publish, but it prefixes the channel
-- with the Reqless namespace
function Reqless.publish(channel, message)
  redis.call('publish', Reqless.ns .. channel, message)
end

-- Return a job object given its job id
function Reqless.job(jid)
  assert(jid, 'Job(): no jid provided')
  local job = {}
  setmetatable(job, ReqlessJob)
  job.jid = jid
  return job
end

-- Return a recurring job object
function Reqless.recurring(jid)
  assert(jid, 'Recurring(): no jid provided')
  local job = {}
  setmetatable(job, ReqlessRecurringJob)
  job.jid = jid
  return job
end

-- Return a throttle object
-- throttle objects are used for arbitrary throttling of jobs.
function Reqless.throttle(tid)
  assert(tid, 'Throttle(): no tid provided')
  local throttle = ReqlessThrottle.data({id = tid})
  setmetatable(throttle, ReqlessThrottle)

  -- set of jids which have acquired a lock on this throttle.
  throttle.locks = {
    length = function()
      return (redis.call('zcard', ReqlessThrottle.ns .. tid .. '-locks') or 0)
    end, members = function()
      return redis.call('zrange', ReqlessThrottle.ns .. tid .. '-locks', 0, -1)
    end, add = function(...)
      if #arg > 0 then
        redis.call('zadd', ReqlessThrottle.ns .. tid .. '-locks', unpack(arg))
      end
    end, remove = function(...)
      if #arg > 0 then
        return redis.call('zrem', ReqlessThrottle.ns .. tid .. '-locks', unpack(arg))
      end
    end, pop = function(min, max)
      return redis.call('zremrangebyrank', ReqlessThrottle.ns .. tid .. '-locks', min, max)
    end, peek = function(min, max)
      return redis.call('zrange', ReqlessThrottle.ns .. tid .. '-locks', min, max)
    end
  }

  -- set of jids which are waiting for the throttle to become available.
  throttle.pending = {
    length = function()
      return (redis.call('zcard', ReqlessThrottle.ns .. tid .. '-pending') or 0)
    end, members = function()
        return redis.call('zrange', ReqlessThrottle.ns .. tid .. '-pending', 0, -1)
    end, add = function(now, jid)
      redis.call('zadd', ReqlessThrottle.ns .. tid .. '-pending', now, jid)
    end, remove = function(...)
      if #arg > 0 then
        return redis.call('zrem', ReqlessThrottle.ns .. tid .. '-pending', unpack(arg))
      end
    end, pop = function(min, max)
      return redis.call('zremrangebyrank', ReqlessThrottle.ns .. tid .. '-pending', min, max)
    end, peek = function(min, max)
      return redis.call('zrange', ReqlessThrottle.ns .. tid .. '-pending', min, max)
    end
  }

  return throttle
end

-- Failed([group, [start, [limit]]])
-- ------------------------------------
-- If no group is provided, this returns a JSON blob of the counts of the
-- various groups of failures known. If a group is provided, it will report up
-- to `limit` from `start` of the jobs affected by that issue.
--
--  # If no group, then...
--  {
--      'group1': 1,
--      'group2': 5,
--      ...
--  }
--
--  # If a group is provided, then...
--  {
--      'total': 20,
--      'jobs': [
--          {
--              # All the normal keys for a job
--              'jid': ...,
--              'data': ...
--              # The message for this particular instance
--              'message': ...,
--              'group': ...,
--          }, ...
--      ]
--  }
--
function Reqless.failed(group, start, limit)
  start = assert(tonumber(start or 0),
    'Failed(): Arg "start" is not a number: ' .. (start or 'nil'))
  limit = assert(tonumber(limit or 25),
    'Failed(): Arg "limit" is not a number: ' .. (limit or 'nil'))

  if group then
    -- If a group was provided, then we should do paginated lookup
    return {
      total = redis.call('llen', 'ql:f:' .. group),
      jobs  = redis.call('lrange', 'ql:f:' .. group, start, start + limit - 1)
    }
  end

  -- Otherwise, we should just list all the known failure groups we have
  local response = {}
  local groups = redis.call('smembers', 'ql:failures')
  for _, group in ipairs(groups) do
    response[group] = redis.call('llen', 'ql:f:' .. group)
  end
  return response
end

-- Jobs(now, 'complete', [offset, [count]])
-- Jobs(now, (
--          'stalled' | 'running' | 'scheduled' | 'depends', 'recurring'
--      ), queue, [offset, [count]])
-------------------------------------------------------------------------------
-- Return all the job ids currently considered to be in the provided state
-- in a particular queue. The response is a list of job ids:
--
--  [
--      jid1,
--      jid2,
--      ...
--  ]
function Reqless.jobs(now, state, ...)
  assert(state, 'Jobs(): Arg "state" missing')
  if state == 'complete' then
    local offset = assert(tonumber(arg[1] or 0),
      'Jobs(): Arg "offset" not a number: ' .. tostring(arg[1]))
    local count  = assert(tonumber(arg[2] or 25),
      'Jobs(): Arg "count" not a number: ' .. tostring(arg[2]))
    return redis.call('zrevrange', 'ql:completed', offset,
      offset + count - 1)
  end

  local queue_name  = assert(arg[1], 'Jobs(): Arg "queue" missing')
  local offset = assert(tonumber(arg[2] or 0),
    'Jobs(): Arg "offset" not a number: ' .. tostring(arg[2]))
  local count  = assert(tonumber(arg[3] or 25),
    'Jobs(): Arg "count" not a number: ' .. tostring(arg[3]))

  local queue = Reqless.queue(queue_name)
  if state == 'running' then
    return queue.locks.peek(now, offset, count)
  elseif state == 'stalled' then
    return queue.locks.expired(now, offset, count)
  elseif state == 'throttled' then
    return queue.throttled.peek(now, offset, count)
  elseif state == 'scheduled' then
    queue:check_scheduled(now, queue.scheduled.length())
    return queue.scheduled.peek(now, offset, count)
  elseif state == 'depends' then
    return queue.depends.peek(now, offset, count)
  elseif state == 'recurring' then
    return queue.recurring.peek(math.huge, offset, count)
  end

  error('Jobs(): Unknown type "' .. state .. '"')
end

-- Track()
-- Track(now, ('track' | 'untrack'), jid)
-- ------------------------------------------
-- If no arguments are provided, it returns details of all currently-tracked
-- jobs. If the first argument is 'track', then it will start tracking the job
-- associated with that id, and 'untrack' stops tracking it. In this context,
-- tracking is nothing more than saving the job to a list of jobs that are
-- considered special.
--
--  {
--      'jobs': [
--          {
--              'jid': ...,
--              # All the other details you'd get from 'job.get'
--          }, {
--              ...
--          }
--      ], 'expired': [
--          # These are all the jids that are completed and whose data expired
--          'deadbeef',
--          ...,
--          ...,
--      ]
--  }
--
function Reqless.track(now, command, jid)
  if command ~= nil then
    assert(jid, 'Track(): Arg "jid" missing')
    -- Verify that job exists
    assert(Reqless.job(jid):exists(), 'Track(): Job does not exist')
    if string.lower(command) == 'track' then
      Reqless.publish('track', jid)
      return redis.call('zadd', 'ql:tracked', now, jid)
    elseif string.lower(command) == 'untrack' then
      Reqless.publish('untrack', jid)
      return redis.call('zrem', 'ql:tracked', jid)
    end
    error('Track(): Unknown action "' .. command .. '"')
  end

  local response = {
    jobs = {},
    expired = {},
  }
  local jids = redis.call('zrange', 'ql:tracked', 0, -1)
  for _, jid in ipairs(jids) do
    local data = Reqless.job(jid):data()
    if data then
      table.insert(response.jobs, data)
    else
      table.insert(response.expired, jid)
    end
  end
  return response
end

-- tag(now, ('add' | 'remove'), jid, tag, [tag, ...])
-- tag(now, 'get', tag, [offset, [count]])
-- tag(now, 'top', [offset, [count]])
-- -----------------------------------------------------------------------------
-- Accepts a jid, 'add' or 'remove', and then a list of tags
-- to either add or remove from the job. Alternatively, 'get',
-- a tag to get jobs associated with that tag, and offset and
-- count
--
-- If 'add' or 'remove', the response is a list of the jobs
-- current tags, or False if the job doesn't exist. If 'get',
-- the response is of the form:
--
--  {
--      total: ...,
--      jobs: [
--          jid,
--          ...
--      ]
--  }
--
-- If 'top' is supplied, it returns the most commonly-used tags
-- in a paginated fashion.
function Reqless.tag(now, command, ...)
  assert(command,
    'Tag(): Arg "command" must be "add", "remove", "get" or "top"')

  if command == 'add' then
    local jid  = assert(arg[1], 'Tag(): Arg "jid" missing')
    local tags = redis.call('hget', ReqlessJob.ns .. jid, 'tags')
    -- If the job has been canceled / deleted, then return false
    if tags then
      -- Decode the json blob, convert to dictionary
      tags = cjson.decode(tags)
      local _tags = {}
      for _, v in ipairs(tags) do _tags[v] = true end

      -- Otherwise, add the job to the sorted set with that tags
      for i=2, #arg do
        local tag = arg[i]
        if _tags[tag] == nil then
          _tags[tag] = true
          table.insert(tags, tag)
        end
        Reqless.job(jid):insert_tag(now, tag)
      end

      redis.call('hset', ReqlessJob.ns .. jid, 'tags', cjson.encode(tags))
      return tags
    end

    error('Tag(): Job ' .. jid .. ' does not exist')
  elseif command == 'remove' then
    local jid  = assert(arg[1], 'Tag(): Arg "jid" missing')
    local tags = redis.call('hget', ReqlessJob.ns .. jid, 'tags')
    -- If the job has been canceled / deleted, then return false
    if tags then
      -- Decode the json blob, convert to dictionary
      tags = cjson.decode(tags)
      local _tags = {}
      for _, v in ipairs(tags) do _tags[v] = true end

      -- Otherwise, remove the job from the sorted set with that tags
      for i=2, #arg do
        local tag = arg[i]
        _tags[tag] = nil
        Reqless.job(jid):remove_tag(tag)
      end

      local results = {}
      for _, tag in ipairs(tags) do
        if _tags[tag] then
          table.insert(results, tag)
        end
      end

      redis.call('hset', ReqlessJob.ns .. jid, 'tags', cjson.encode(results))
      return results
    end
    error('Tag(): Job ' .. jid .. ' does not exist')
  elseif command == 'get' then
    local tag    = assert(arg[1], 'Tag(): Arg "tag" missing')
    local offset = assert(tonumber(arg[2] or 0),
      'Tag(): Arg "offset" not a number: ' .. tostring(arg[2]))
    local count  = assert(tonumber(arg[3] or 25),
      'Tag(): Arg "count" not a number: ' .. tostring(arg[3]))
    return {
      total = redis.call('zcard', 'ql:t:' .. tag),
      jobs  = redis.call('zrange', 'ql:t:' .. tag, offset, offset + count - 1)
    }
  elseif command == 'top' then
    local offset = assert(tonumber(arg[1] or 0) , 'Tag(): Arg "offset" not a number: ' .. tostring(arg[1]))
    local count  = assert(tonumber(arg[2] or 25), 'Tag(): Arg "count" not a number: ' .. tostring(arg[2]))
    return redis.call('zrevrangebyscore', 'ql:tags', '+inf', 2, 'limit', offset, count)
  end

  error('Tag(): First argument must be "add", "remove" or "get"')
end

-- Cancel(...)
-- --------------
-- Cancel a job from taking place. It will be deleted from the system, and any
-- attempts to renew a heartbeat will fail, and any attempts to complete it
-- will fail. If you try to get the data on the object, you will get nothing.
function Reqless.cancel(now, ...)
  -- Dependents is a mapping of a job to its dependent jids
  local dependents = {}
  for _, jid in ipairs(arg) do
    dependents[jid] = redis.call(
      'smembers', ReqlessJob.ns .. jid .. '-dependents') or {}
  end

  -- Now, we'll loop through every jid we intend to cancel, and we'll go
  -- make sure that this operation will be ok
  for _, jid in ipairs(arg) do
    for j, dep in ipairs(dependents[jid]) do
      if dependents[dep] == nil then
        error('Cancel(): ' .. jid .. ' is a dependency of ' .. dep ..
           ' but is not mentioned to be canceled')
      end
    end
  end

  -- If we've made it this far, then we are good to go. We can now just
  -- remove any trace of all these jobs, as they form a dependent clique
  for _, jid in ipairs(arg) do
    -- Find any stage it's associated with and remove its from that stage
    local state, queue, failure, worker = unpack(redis.call(
      'hmget', ReqlessJob.ns .. jid, 'state', 'queue', 'failure', 'worker'))

    if state ~= 'complete' then
      -- Send a message out on the appropriate channels
      local encoded = cjson.encode({
        jid    = jid,
        worker = worker,
        event  = 'canceled',
        queue  = queue
      })
      Reqless.publish('log', encoded)

      -- Remove this job from whatever worker has it, if any
      if worker and (worker ~= '') then
        redis.call('zrem', 'ql:w:' .. worker .. ':jobs', jid)
        -- If necessary, send a message to the appropriate worker, too
        Reqless.publish('w:' .. worker, encoded)
      end

      -- Remove it from that queue
      if queue then
        local queue = Reqless.queue(queue)
        queue:remove_job(jid)
      end

      local job = Reqless.job(jid)

      job:throttles_release(now)

      -- We should probably go through all our dependencies and remove
      -- ourselves from the list of dependents
      for _, j in ipairs(redis.call(
        'smembers', ReqlessJob.ns .. jid .. '-dependencies')) do
        redis.call('srem', ReqlessJob.ns .. j .. '-dependents', jid)
      end

      -- If we're in the failed state, remove all of our data
      if state == 'failed' then
        failure = cjson.decode(failure)
        -- We need to make this remove it from the failed queues
        redis.call('lrem', 'ql:f:' .. failure.group, 0, jid)
        if redis.call('llen', 'ql:f:' .. failure.group) == 0 then
          redis.call('srem', 'ql:failures', failure.group)
        end
        -- Remove one count from the failed count of the particular
        -- queue
        local bin = failure.when - (failure.when % 86400)
        local failed = redis.call(
          'hget', 'ql:s:stats:' .. bin .. ':' .. queue, 'failed')
        redis.call('hset',
          'ql:s:stats:' .. bin .. ':' .. queue, 'failed', failed - 1)
      end

      job:delete()

      -- If the job was being tracked, we should notify
      if redis.call('zscore', 'ql:tracked', jid) ~= false then
        Reqless.publish('canceled', jid)
      end
    end
  end

  return arg
end
-------------------------------------------------------------------------------
-- Configuration interactions
-------------------------------------------------------------------------------

-- This represents our default configuration settings
Reqless.config.defaults = {
  ['application']        = 'reqless',
  ['grace-period']       = 10,
  ['heartbeat']          = 60,
  ['jobs-history']       = 604800,
  ['jobs-history-count'] = 50000,
  ['max-job-history']    = 100,
  ['max-pop-retry']      = 1,
  ['max-worker-age']     = 86400,
}

-- Get one or more of the keys
Reqless.config.get = function(key, default)
  if key then
    return redis.call('hget', 'ql:config', key) or
      Reqless.config.defaults[key] or default
  end

  -- Inspired by redis-lua https://github.com/nrk/redis-lua/blob/version-2.0/src/redis.lua
  local reply = redis.call('hgetall', 'ql:config')
  for i = 1, #reply, 2 do
    Reqless.config.defaults[reply[i]] = reply[i + 1]
  end
  return Reqless.config.defaults
end

-- Set a configuration variable
Reqless.config.set = function(option, value)
  assert(option, 'config.set(): Arg "option" missing')
  assert(value , 'config.set(): Arg "value" missing')
  -- Send out a log message
  Reqless.publish('log', cjson.encode({
    event  = 'config_set',
    option = option,
    value  = value
  }))

  redis.call('hset', 'ql:config', option, value)
end

-- Unset a configuration option
Reqless.config.unset = function(option)
  assert(option, 'config.unset(): Arg "option" missing')
  -- Send out a log message
  Reqless.publish('log', cjson.encode({
    event  = 'config_unset',
    option = option
  }))

  redis.call('hdel', 'ql:config', option)
end
-------------------------------------------------------------------------------
-- Job Class
--
-- It returns an object that represents the job with the provided JID
-------------------------------------------------------------------------------

-- This gets all the data associated with the job with the provided id. If the
-- job is not found, it returns nil. If found, it returns an object with the
-- appropriate properties
function ReqlessJob:data(...)
  local job = redis.call(
      'hmget', ReqlessJob.ns .. self.jid, 'jid', 'klass', 'state', 'queue',
      'worker', 'priority', 'expires', 'retries', 'remaining', 'data',
      'tags', 'failure', 'throttles', 'spawned_from_jid')

  -- Return nil if we haven't found it
  if not job[1] then
    return nil
  end

  local data = {
    jid = job[1],
    klass = job[2],
    state = job[3],
    queue = job[4],
    worker = job[5] or '',
    tracked = redis.call('zscore', 'ql:tracked', self.jid) ~= false,
    priority = tonumber(job[6]),
    expires = tonumber(job[7]) or 0,
    retries = tonumber(job[8]),
    remaining = math.floor(tonumber(job[9])),
    data = job[10],
    tags = cjson.decode(job[11]),
    history = self:history(),
    failure = cjson.decode(job[12] or '{}'),
    throttles = cjson.decode(job[13] or '[]'),
    spawned_from_jid = job[14],
    dependents = redis.call('smembers', ReqlessJob.ns .. self.jid .. '-dependents'),
    dependencies = redis.call('smembers', ReqlessJob.ns .. self.jid .. '-dependencies'),
  }

  if #arg > 0 then
    -- This section could probably be optimized, but I wanted the interface
    -- in place first
    local response = {}
    for _, key in ipairs(arg) do
      table.insert(response, data[key])
    end
    return response
  end

  return data
end

-- Complete a job and optionally put it in another queue, either scheduled or
-- to be considered waiting immediately. It can also optionally accept other
-- jids on which this job will be considered dependent before it's considered
-- valid.
--
-- The variable-length arguments may be pairs of the form:
--
--      ('next'   , queue) : The queue to advance it to next
--      ('delay'  , delay) : The delay for the next queue
--      ('depends',        : Json of jobs it depends on in the new queue
--          '["jid1", "jid2", ...]')
---
function ReqlessJob:complete(now, worker, queue_name, raw_data, ...)
  assert(worker, 'Complete(): Arg "worker" missing')
  assert(queue_name , 'Complete(): Arg "queue_name" missing')
  local data = assert(cjson.decode(raw_data),
    'Complete(): Arg "data" missing or not JSON: ' .. tostring(raw_data))

  -- Read in all the optional parameters
  local options = {}
  for i = 1, #arg, 2 do options[arg[i]] = arg[i + 1] end

  -- Sanity check on optional args
  local next_queue_name = options['next']
  local delay = assert(tonumber(options['delay'] or 0))
  local depends = assert(cjson.decode(options['depends'] or '[]'),
    'Complete(): Arg "depends" not JSON: ' .. tostring(options['depends']))

  -- Delay doesn't make sense without next_queue_name
  if options['delay'] and next_queue_name == nil then
    error('Complete(): "delay" cannot be used without a "next".')
  end

  -- Depends doesn't make sense without next_queue_name
  if options['depends'] and next_queue_name == nil then
    error('Complete(): "depends" cannot be used without a "next".')
  end

  -- The bin is midnight of the provided day
  -- 24 * 60 * 60 = 86400
  local bin = now - (now % 86400)

  -- First things first, we should see if the worker still owns this job
  local lastworker, state, priority, retries, current_queue = unpack(
    redis.call('hmget', ReqlessJob.ns .. self.jid, 'worker', 'state',
      'priority', 'retries', 'queue'))

  if lastworker == false then
    error('Complete(): Job does not exist')
  elseif (state ~= 'running') then
    error('Complete(): Job is not currently running: ' .. state)
  elseif lastworker ~= worker then
    error('Complete(): Job has been handed out to another worker: ' ..
      tostring(lastworker))
  elseif queue_name ~= current_queue then
    error('Complete(): Job running in another queue: ' ..
      tostring(current_queue))
  end

  -- Now we can assume that the worker does own the job. We need to
  --    1) Remove the job from the 'locks' from the old queue
  --    2) Enqueue it in the next stage if necessary
  --    3) Update the data
  --    4) Mark the job as completed, remove the worker, remove expires, and
  --          update history
  self:history(now, 'done')

  redis.call('hset', ReqlessJob.ns .. self.jid, 'data', raw_data)

  -- Remove the job from the previous queue
  local queue = Reqless.queue(queue_name)
  queue:remove_job(self.jid)

  self:throttles_release(now)

  ----------------------------------------------------------
  -- This is the massive stats update that we have to do
  ----------------------------------------------------------
  -- This is how long we've been waiting to get popped
  -- local waiting = math.floor(now) - history[#history]['popped']
  local time = tonumber(
    redis.call('hget', ReqlessJob.ns .. self.jid, 'time') or now)
  local waiting = now - time
  queue:stat(now, 'run', waiting)
  redis.call('hset', ReqlessJob.ns .. self.jid,
    'time', string.format("%.20f", now))

  -- Remove this job from the jobs that the worker that was running it has
  redis.call('zrem', 'ql:w:' .. worker .. ':jobs', self.jid)

  if redis.call('zscore', 'ql:tracked', self.jid) ~= false then
    Reqless.publish('completed', self.jid)
  end

  if next_queue_name then
    local next_queue = Reqless.queue(next_queue_name)
    -- Send a message out to log
    Reqless.publish('log', cjson.encode({
      jid = self.jid,
      event = 'advanced',
      queue = queue_name,
      to = next_queue_name,
    }))

    -- Enqueue the job
    self:history(now, 'put', {queue = next_queue_name})

    -- We're going to make sure that this queue is in the
    -- set of known queues
    if redis.call('zscore', 'ql:queues', next_queue_name) == false then
      redis.call('zadd', 'ql:queues', now, next_queue_name)
    end

    redis.call('hmset', ReqlessJob.ns .. self.jid,
      'state', 'waiting',
      'worker', '',
      'failure', '{}',
      'queue', next_queue_name,
      'expires', 0,
      'remaining', tonumber(retries))

    if (delay > 0) and (#depends == 0) then
      next_queue.scheduled.add(now + delay, self.jid)
      return 'scheduled'
    end

    -- These are the jids we legitimately have to wait on
    local count = 0
    for _, j in ipairs(depends) do
      -- Make sure it's something other than 'nil' or complete.
      local state = redis.call('hget', ReqlessJob.ns .. j, 'state')
      if (state and state ~= 'complete') then
        count = count + 1
        redis.call(
          'sadd', ReqlessJob.ns .. j .. '-dependents',self.jid)
        redis.call(
          'sadd', ReqlessJob.ns .. self.jid .. '-dependencies', j)
      end
    end
    if count > 0 then
      next_queue.depends.add(now, self.jid)
      redis.call('hset', ReqlessJob.ns .. self.jid, 'state', 'depends')
      if delay > 0 then
        -- We've already put it in 'depends'. Now, we must just save the data
        -- for when it's scheduled
        next_queue.depends.add(now, self.jid)
        redis.call('hset', ReqlessJob.ns .. self.jid, 'scheduled', now + delay)
      end
      return 'depends'
    end

    next_queue.work.add(now, priority, self.jid)
    return 'waiting'
  end
  -- Send a message out to log
  Reqless.publish('log', cjson.encode({
    jid = self.jid,
    event = 'completed',
    queue = queue_name,
  }))

  redis.call('hmset', ReqlessJob.ns .. self.jid,
    'state', 'complete',
    'worker', '',
    'failure', '{}',
    'queue', '',
    'expires', 0,
    'remaining', tonumber(retries))

  -- Do the completion dance
  local count = Reqless.config.get('jobs-history-count')
  local time  = Reqless.config.get('jobs-history')

  -- These are the default values
  count = tonumber(count or 50000)
  time  = tonumber(time  or 7 * 24 * 60 * 60)

  -- Schedule this job for destructination eventually
  redis.call('zadd', 'ql:completed', now, self.jid)

  -- Now look at the expired job data. First, based on the current time
  local jids = redis.call('zrangebyscore', 'ql:completed', 0, now - time)
  -- Any jobs that need to be expired... delete
  for _, jid in ipairs(jids) do
    Reqless.job(jid):delete()
  end

  -- And now remove those from the queued-for-cleanup queue
  redis.call('zremrangebyscore', 'ql:completed', 0, now - time)

  -- Now take the all by the most recent 'count' ids
  jids = redis.call('zrange', 'ql:completed', 0, (-1-count))
  for _, jid in ipairs(jids) do
    Reqless.job(jid):delete()
  end
  redis.call('zremrangebyrank', 'ql:completed', 0, (-1-count))

  -- Alright, if this has any dependents, then we should go ahead
  -- and unstick those guys.
  for _, j in ipairs(redis.call(
    'smembers', ReqlessJob.ns .. self.jid .. '-dependents')) do
    redis.call('srem', ReqlessJob.ns .. j .. '-dependencies', self.jid)
    if redis.call(
      'scard', ReqlessJob.ns .. j .. '-dependencies') == 0 then
      local other_queue_name, priority, scheduled = unpack(
        redis.call('hmget', ReqlessJob.ns .. j, 'queue', 'priority', 'scheduled'))
      if other_queue_name then
        local other_queue = Reqless.queue(other_queue_name)
        other_queue.depends.remove(j)
        if scheduled then
          other_queue.scheduled.add(scheduled, j)
          redis.call('hset', ReqlessJob.ns .. j, 'state', 'scheduled')
          redis.call('hdel', ReqlessJob.ns .. j, 'scheduled')
        else
          other_queue.work.add(now, priority, j)
          redis.call('hset', ReqlessJob.ns .. j, 'state', 'waiting')
        end
      end
    end
  end

  -- Delete our dependents key
  redis.call('del', ReqlessJob.ns .. self.jid .. '-dependents')

  return 'complete'
end

-- Fail(now, worker, group, message, [data])
-- -------------------------------------------------
-- Mark the particular job as failed, with the provided group, and a more
-- specific message. By `group`, we mean some phrase that might be one of
-- several categorical modes of failure. The `message` is something more
-- job-specific, like perhaps a traceback.
--
-- This method should __not__ be used to note that a job has been dropped or
-- has failed in a transient way. This method __should__ be used to note that
-- a job has something really wrong with it that must be remedied.
--
-- The motivation behind the `group` is so that similar errors can be grouped
-- together. Optionally, updated data can be provided for the job. A job in
-- any state can be marked as failed. If it has been given to a worker as a
-- job, then its subsequent requests to heartbeat or complete that job will
-- fail. Failed jobs are kept until they are canceled or completed.
--
-- __Returns__ the id of the failed job if successful, or `False` on failure.
--
-- Args:
--    1) jid
--    2) worker
--    3) group
--    4) message
--    5) the current time
--    6) [data]
function ReqlessJob:fail(now, worker, group, message, data)
  local worker  = assert(worker           , 'Fail(): Arg "worker" missing')
  local group   = assert(group            , 'Fail(): Arg "group" missing')
  local message = assert(message          , 'Fail(): Arg "message" missing')

  -- The bin is midnight of the provided day
  -- 24 * 60 * 60 = 86400
  local bin = now - (now % 86400)

  if data then
    data = cjson.decode(data)
  end

  -- First things first, we should get the history
  local queue_name, state, oldworker = unpack(redis.call(
    'hmget', ReqlessJob.ns .. self.jid, 'queue', 'state', 'worker'))

  -- If the job has been completed, we cannot fail it
  if not state then
    error('Fail(): Job does not exist')
  elseif state ~= 'running' then
    error('Fail(): Job not currently running: ' .. state)
  elseif worker ~= oldworker then
    error('Fail(): Job running with another worker: ' .. oldworker)
  end

  -- Send out a log message
  Reqless.publish('log', cjson.encode({
    jid = self.jid,
    event = 'failed',
    worker = worker,
    group = group,
    message = message,
  }))

  if redis.call('zscore', 'ql:tracked', self.jid) ~= false then
    Reqless.publish('failed', self.jid)
  end

  -- Remove this job from the jobs that the worker that was running it has
  redis.call('zrem', 'ql:w:' .. worker .. ':jobs', self.jid)

  -- Now, take the element of the history for which our provided worker is
  -- the worker, and update 'failed'
  self:history(now, 'failed', {worker = worker, group = group})

  -- Increment the number of failures for that queue for the
  -- given day.
  redis.call('hincrby', 'ql:s:stats:' .. bin .. ':' .. queue_name, 'failures', 1)
  redis.call('hincrby', 'ql:s:stats:' .. bin .. ':' .. queue_name, 'failed'  , 1)

  -- Now remove the instance from the schedule, and work queues for the
  -- queue it's in
  local queue = Reqless.queue(queue_name)
  queue:remove_job(self.jid)

  -- The reason that this appears here is that the above will fail if the
  -- job doesn't exist
  if data then
    redis.call('hset', ReqlessJob.ns .. self.jid, 'data', cjson.encode(data))
  end

  redis.call('hmset', ReqlessJob.ns .. self.jid,
    'state', 'failed',
    'worker', '',
    'expires', '',
    'failure', cjson.encode({
      group   = group,
      message = message,
      when    = math.floor(now),
      worker  = worker
    }))

  self:throttles_release(now)

  -- Add this group of failure to the list of failures
  redis.call('sadd', 'ql:failures', group)
  -- And add this particular instance to the failed groups
  redis.call('lpush', 'ql:f:' .. group, self.jid)

  -- Here is where we'd increment stats about the particular stage
  -- and possibly the workers

  return self.jid
end

-- retry(now, queue_name, worker, [delay, [group, [message]]])
-- ------------------------------------------
-- This script accepts jid, queue, worker and delay for retrying a job. This
-- is similar in functionality to `put`, except that this counts against the
-- retries a job has for a stage.
--
-- Throws an exception if:
--      - the worker is not the worker with a lock on the job
--      - the job is not actually running
--
-- Otherwise, it returns the number of retries remaining. If the allowed
-- retries have been exhausted, then it is automatically failed, and a negative
-- number is returned.
--
-- If a group and message is provided, then if the retries are exhausted, then
-- the provided group and message will be used in place of the default
-- messaging about retries in the particular queue being exhausted
function ReqlessJob:retry(now, queue_name, worker, delay, group, message)
  assert(queue_name , 'Retry(): Arg "queue_name" missing')
  assert(worker, 'Retry(): Arg "worker" missing')
  delay = assert(tonumber(delay or 0),
    'Retry(): Arg "delay" not a number: ' .. tostring(delay))

  -- Let's see what the old priority, and tags were
  local old_queue_name, state, retries, oldworker, priority, failure = unpack(
    redis.call('hmget', ReqlessJob.ns .. self.jid, 'queue', 'state',
      'retries', 'worker', 'priority', 'failure'))

  -- If this isn't the worker that owns
  if oldworker == false then
    error('Retry(): Job does not exist')
  elseif state ~= 'running' then
    error('Retry(): Job is not currently running: ' .. state)
  elseif oldworker ~= worker then
    error('Retry(): Job has been given to another worker: ' .. oldworker)
  end

  -- For each of these, decrement their retries. If any of them
  -- have exhausted their retries, then we should mark them as
  -- failed.
  local remaining = tonumber(redis.call(
    'hincrby', ReqlessJob.ns .. self.jid, 'remaining', -1))
  redis.call('hdel', ReqlessJob.ns .. self.jid, 'grace')

  -- Remove it from the locks key of the old queue
  Reqless.queue(old_queue_name).locks.remove(self.jid)

  -- Release the throttle for the job
  self:throttles_release(now)

  -- Remove this job from the worker that was previously working it
  redis.call('zrem', 'ql:w:' .. worker .. ':jobs', self.jid)

  if remaining < 0 then
    -- Now remove the instance from the schedule, and work queues for the
    -- queue it's in
    local group = group or 'failed-retries-' .. queue_name
    self:history(now, 'failed-retries', {group = group})

    redis.call('hmset', ReqlessJob.ns .. self.jid, 'state', 'failed',
      'worker', '',
      'expires', '')
    -- If the failure has not already been set, then set it
    if group ~= nil and message ~= nil then
      redis.call('hset', ReqlessJob.ns .. self.jid,
        'failure', cjson.encode({
          group   = group,
          message = message,
          when    = math.floor(now),
          worker  = worker
        })
      )
    else
      redis.call('hset', ReqlessJob.ns .. self.jid,
      'failure', cjson.encode({
        group   = group,
        message = 'Job exhausted retries in queue "' .. old_queue_name .. '"',
        when    = now,
        worker  = unpack(self:data('worker'))
      }))
    end

    -- Add this type of failure to the list of failures
    redis.call('sadd', 'ql:failures', group)
    -- And add this particular instance to the failed types
    redis.call('lpush', 'ql:f:' .. group, self.jid)
    -- Increment the count of the failed jobs
    local bin = now - (now % 86400)
    redis.call('hincrby', 'ql:s:stats:' .. bin .. ':' .. queue_name, 'failures', 1)
    redis.call('hincrby', 'ql:s:stats:' .. bin .. ':' .. queue_name, 'failed'  , 1)
  else
    -- Put it in the queue again with a delay. Like put()
    local queue = Reqless.queue(queue_name)
    if delay > 0 then
      queue.scheduled.add(now + delay, self.jid)
      redis.call('hset', ReqlessJob.ns .. self.jid, 'state', 'scheduled')
    else
      queue.work.add(now, priority, self.jid)
      redis.call('hset', ReqlessJob.ns .. self.jid, 'state', 'waiting')
    end

    -- If a group and a message was provided, then we should save it
    if group ~= nil and message ~= nil then
      redis.call('hset', ReqlessJob.ns .. self.jid,
        'failure', cjson.encode({
          group   = group,
          message = message,
          when    = math.floor(now),
          worker  = worker
        })
      )
    end
  end

  return math.floor(remaining)
end

-- Depends(jid, 'on', [jid, [jid, [...]]]
-- Depends(jid, 'off', [jid, [jid, [...]]])
-- Depends(jid, 'off', 'all')
-------------------------------------------------------------------------------
-- Add or remove dependencies a job has. If 'on' is provided, the provided
-- jids are added as dependencies. If 'off' and 'all' are provided, then all
-- the current dependencies are removed. If 'off' is provided and the next
-- argument is not 'all', then those jids are removed as dependencies.
--
-- If a job is not already in the 'depends' state, then this call will raise an
-- error.  Otherwise, it will return true.
function ReqlessJob:depends(now, command, ...)
  assert(command, 'Depends(): Arg "command" missing')
  if command ~= 'on' and command ~= 'off' then
    error('Depends(): Argument "command" must be "on" or "off"')
  end

  local state = redis.call('hget', ReqlessJob.ns .. self.jid, 'state')
  if state ~= 'depends' then
    error('Depends(): Job ' .. self.jid ..
      ' not in the depends state: ' .. tostring(state))
  end

  if command == 'on' then
    -- These are the jids we legitimately have to wait on
    for _, j in ipairs(arg) do
      -- Make sure it's something other than 'nil' or complete.
      local state = redis.call('hget', ReqlessJob.ns .. j, 'state')
      if (state and state ~= 'complete') then
        redis.call(
          'sadd', ReqlessJob.ns .. j .. '-dependents'  , self.jid)
        redis.call(
          'sadd', ReqlessJob.ns .. self.jid .. '-dependencies', j)
      end
    end
    return true
  end

  if arg[1] == 'all' then
    for _, j in ipairs(redis.call(
      'smembers', ReqlessJob.ns .. self.jid .. '-dependencies')) do
      redis.call('srem', ReqlessJob.ns .. j .. '-dependents', self.jid)
    end
    redis.call('del', ReqlessJob.ns .. self.jid .. '-dependencies')
    local queue_name, priority = unpack(redis.call(
      'hmget', ReqlessJob.ns .. self.jid, 'queue', 'priority'))
    if queue_name then
      local queue = Reqless.queue(queue_name)
      queue.depends.remove(self.jid)
      queue.work.add(now, priority, self.jid)
      redis.call('hset', ReqlessJob.ns .. self.jid, 'state', 'waiting')
    end
  else
    for _, j in ipairs(arg) do
      redis.call('srem', ReqlessJob.ns .. j .. '-dependents', self.jid)
      redis.call(
        'srem', ReqlessJob.ns .. self.jid .. '-dependencies', j)
      if redis.call('scard',
        ReqlessJob.ns .. self.jid .. '-dependencies') == 0 then
        local queue_name, priority = unpack(redis.call(
          'hmget', ReqlessJob.ns .. self.jid, 'queue', 'priority'))
        if queue_name then
          local queue = Reqless.queue(queue_name)
          queue.depends.remove(self.jid)
          queue.work.add(now, priority, self.jid)
          redis.call('hset',
            ReqlessJob.ns .. self.jid, 'state', 'waiting')
        end
      end
    end
  end
  return true
end

-- Heartbeat
------------
-- Renew this worker's lock on this job. Throws an exception if:
--      - the job's been given to another worker
--      - the job's been completed
--      - the job's been canceled
--      - the job's not running
function ReqlessJob:heartbeat(now, worker, data)
  assert(worker, 'Heatbeat(): Arg "worker" missing')

  -- We should find the heartbeat interval for this queue
  -- heartbeat. First, though, we need to find the queue
  -- this particular job is in
  local queue_name = redis.call('hget', ReqlessJob.ns .. self.jid, 'queue') or ''
  local expires = now + tonumber(
    Reqless.config.get(queue_name .. '-heartbeat') or
    Reqless.config.get('heartbeat', 60))

  if data then
    data = cjson.decode(data)
  end

  -- First, let's see if the worker still owns this job, and there is a
  -- worker
  local job_worker, state = unpack(
    redis.call('hmget', ReqlessJob.ns .. self.jid, 'worker', 'state'))
  if job_worker == false then
    -- This means the job doesn't exist
    error('Heartbeat(): Job does not exist')
  elseif state ~= 'running' then
    error('Heartbeat(): Job not currently running: ' .. state)
  elseif job_worker ~= worker or #job_worker == 0 then
    error('Heartbeat(): Job given out to another worker: ' .. job_worker)
  end

  -- Otherwise, optionally update the user data, and the heartbeat
  if data then
    -- I don't know if this is wise, but I'm decoding and encoding
    -- the user data to hopefully ensure its sanity
    redis.call('hmset', ReqlessJob.ns .. self.jid, 'expires',
      expires, 'worker', worker, 'data', cjson.encode(data))
  else
    redis.call('hmset', ReqlessJob.ns .. self.jid,
      'expires', expires, 'worker', worker)
  end

  -- Update hwen this job was last updated on that worker
  -- Add this job to the list of jobs handled by this worker
  redis.call('zadd', 'ql:w:' .. worker .. ':jobs', expires, self.jid)

  -- And now we should just update the locks
  local queue = Reqless.queue(
    redis.call('hget', ReqlessJob.ns .. self.jid, 'queue'))
  queue.locks.add(expires, self.jid)
  return expires
end

-- Priority
-- --------
-- Update the priority of this job. If the job doesn't exist, throws an
-- exception
function ReqlessJob:priority(priority)
  priority = assert(tonumber(priority),
    'Priority(): Arg "priority" missing or not a number: ' ..
    tostring(priority))

  -- Get the queue the job is currently in, if any
  local queue_name = redis.call('hget', ReqlessJob.ns .. self.jid, 'queue')

  if queue_name == nil then
    -- If the job doesn't exist, throw an error
    error('Priority(): Job ' .. self.jid .. ' does not exist')
  end

  -- See if the job is a candidate for updating its priority in the queue it's
  -- currently in
  if queue_name ~= '' then
    local queue = Reqless.queue(queue_name)
    if queue.work.score(self.jid) then
      queue.work.add(0, priority, self.jid)
    end
  end

  redis.call('hset', ReqlessJob.ns .. self.jid, 'priority', priority)
  return priority
end

-- Update the jobs' attributes with the provided dictionary
function ReqlessJob:update(data)
  local tmp = {}
  for k, v in pairs(data) do
    table.insert(tmp, k)
    table.insert(tmp, v)
  end
  redis.call('hmset', ReqlessJob.ns .. self.jid, unpack(tmp))
end

-- Times out the job now rather than when its lock is normally set to expire
function ReqlessJob:timeout(now)
  local queue_name, state, worker = unpack(redis.call('hmget',
    ReqlessJob.ns .. self.jid, 'queue', 'state', 'worker'))
  if queue_name == nil then
    error('Timeout(): Job does not exist')
  elseif state ~= 'running' then
    error('Timeout(): Job ' .. self.jid .. ' not running')
  end
  -- Time out the job
  self:history(now, 'timed-out')
  local queue = Reqless.queue(queue_name)
  queue.locks.remove(self.jid)

  -- Release acquired throttles
  self:throttles_release(now)

  queue.work.add(now, math.huge, self.jid)
  redis.call('hmset', ReqlessJob.ns .. self.jid,
    'state', 'stalled', 'expires', 0)
  local encoded = cjson.encode({
    jid = self.jid,
    event = 'lock_lost',
    worker = worker,
  })
  Reqless.publish('w:' .. worker, encoded)
  Reqless.publish('log', encoded)
  return queue_name
end

-- Return whether or not this job exists
function ReqlessJob:exists()
  return redis.call('exists', ReqlessJob.ns .. self.jid) == 1
end

-- Get or append to history
function ReqlessJob:history(now, what, item)
  -- First, check if there's an old-style history, and update it if there is
  local history = redis.call('hget', ReqlessJob.ns .. self.jid, 'history')
  if history then
    history = cjson.decode(history)
    for _, value in ipairs(history) do
      redis.call('rpush', ReqlessJob.ns .. self.jid .. '-history',
        cjson.encode({math.floor(value.put), 'put', {queue = value.queue}}))

      -- If there's any popped time
      if value.popped then
        redis.call('rpush', ReqlessJob.ns .. self.jid .. '-history',
          cjson.encode({math.floor(value.popped), 'popped',
            {worker = value.worker}}))
      end

      -- If there's any failure
      if value.failed then
        redis.call('rpush', ReqlessJob.ns .. self.jid .. '-history',
          cjson.encode(
            {math.floor(value.failed), 'failed', nil}))
      end

      -- If it was completed
      if value.done then
        redis.call('rpush', ReqlessJob.ns .. self.jid .. '-history',
          cjson.encode(
            {math.floor(value.done), 'done', nil}))
      end
    end
    -- With all this ported forward, delete the old-style history
    redis.call('hdel', ReqlessJob.ns .. self.jid, 'history')
  end

  -- Now to the meat of the function
  if what == nil then
    -- Get the history
    local response = {}
    for _, value in ipairs(redis.call('lrange',
      ReqlessJob.ns .. self.jid .. '-history', 0, -1)) do
      value = cjson.decode(value)
      local dict = value[3] or {}
      dict['when'] = value[1]
      dict['what'] = value[2]
      table.insert(response, dict)
    end
    return response
  end

  -- Append to the history. If the length of the history should be limited,
  -- then we'll truncate it.
  local count = tonumber(Reqless.config.get('max-job-history', 100))
  if count > 0 then
    -- We'll always keep the first item around
    local obj = redis.call('lpop', ReqlessJob.ns .. self.jid .. '-history')
    redis.call('ltrim', ReqlessJob.ns .. self.jid .. '-history', -count + 2, -1)
    if obj ~= nil and obj ~= false then
      redis.call('lpush', ReqlessJob.ns .. self.jid .. '-history', obj)
    end
  end
  return redis.call('rpush', ReqlessJob.ns .. self.jid .. '-history',
    cjson.encode({math.floor(now), what, item}))
end

function ReqlessJob:throttles_release(now)
  local throttles = redis.call('hget', ReqlessJob.ns .. self.jid, 'throttles')
  throttles = cjson.decode(throttles or '[]')

  for _, tid in ipairs(throttles) do
    Reqless.throttle(tid):release(now, self.jid)
  end
end

function ReqlessJob:throttles_available()
  for _, tid in ipairs(self:throttles()) do
    if not Reqless.throttle(tid):available() then
      return false
    end
  end

  return true
end

function ReqlessJob:throttles_acquire(now)
  if not self:throttles_available() then
    return false
  end

  for _, tid in ipairs(self:throttles()) do
    Reqless.throttle(tid):acquire(self.jid)
  end

  return true
end

-- Finds the first unavailable throttle and adds the job to its pending job set.
function ReqlessJob:throttle(now)
  for _, tid in ipairs(self:throttles()) do
    local throttle = Reqless.throttle(tid)
    if not throttle:available() then
      throttle:pend(now, self.jid)
      return
    end
  end
end

function ReqlessJob:throttles()
  -- memoize throttles for the job.
  if not self._throttles then
    self._throttles = cjson.decode(redis.call('hget', ReqlessJob.ns .. self.jid, 'throttles') or '[]')
  end

  return self._throttles
end

-- Completely removes all the data
-- associated with this job, use
-- with care.
function ReqlessJob:delete()
  local tags = redis.call('hget', ReqlessJob.ns .. self.jid, 'tags') or '[]'
  tags = cjson.decode(tags)
  -- remove the jid from each tag
  for _, tag in ipairs(tags) do
    self:remove_tag(tag)
  end
  -- Delete the job's data
  redis.call('del', ReqlessJob.ns .. self.jid)
  -- Delete the job's history
  redis.call('del', ReqlessJob.ns .. self.jid .. '-history')
  -- Delete any notion of dependencies it has
  redis.call('del', ReqlessJob.ns .. self.jid .. '-dependencies')
end

-- Inserts the jid into the specified tag.
-- This should probably be moved to its own tag
-- object.
function ReqlessJob:insert_tag(now, tag)
  redis.call('zadd', 'ql:t:' .. tag, now, self.jid)
  redis.call('zincrby', 'ql:tags', 1, tag)
end

-- Removes the jid from the specified tag.
-- this should probably be moved to its own tag
-- object.
function ReqlessJob:remove_tag(tag)
  -- namespace the tag
  local namespaced_tag = 'ql:t:' .. tag

  -- Remove the job from the specified tag
  redis.call('zrem', namespaced_tag, self.jid)

  -- Check if any tags jids remain in the tag set.
  local remaining = redis.call('zcard', namespaced_tag)

  -- If the number of jids in the tagged set
  -- is 0 it means we have no jobs with this tag
  -- and we should remove it from the set of all tags
  -- to prevent memory leaks.
  if tonumber(remaining) == 0 then
    redis.call('zrem', 'ql:tags', tag)
  else
    -- Decrement the tag in the set of all tags.
    redis.call('zincrby', 'ql:tags', -1, tag)
  end
end
-------------------------------------------------------------------------------
-- Queue class
-------------------------------------------------------------------------------
-- Return a queue object
function Reqless.queue(name)
  assert(name, 'Queue(): no queue name provided')
  local queue = {}
  setmetatable(queue, ReqlessQueue)
  queue.name = name

  -- Access to our work
  queue.work = {
    peek = function(offset, count)
      if count <= 0 then
        return {}
      end
      return redis.call('zrevrange', queue:prefix('work'), offset, offset + count - 1)
    end, remove = function(...)
      if #arg > 0 then
        return redis.call('zrem', queue:prefix('work'), unpack(arg))
      end
    end, add = function(now, priority, jid)
      return redis.call('zadd',
        queue:prefix('work'), priority - (now / 10000000000), jid)
    end, score = function(jid)
      return redis.call('zscore', queue:prefix('work'), jid)
    end, length = function()
      return redis.call('zcard', queue:prefix('work'))
    end
  }

  -- Access to our locks
  queue.locks = {
    expired = function(now, offset, count)
      return redis.call('zrangebyscore',
        queue:prefix('locks'), -math.huge, now, 'LIMIT', offset, count)
    end, peek = function(now, offset, count)
      return redis.call('zrangebyscore', queue:prefix('locks'),
        now, math.huge, 'LIMIT', offset, count)
    end, add = function(expires, jid)
      redis.call('zadd', queue:prefix('locks'), expires, jid)
    end, remove = function(...)
      if #arg > 0 then
        return redis.call('zrem', queue:prefix('locks'), unpack(arg))
      end
    end, running = function(now)
      return redis.call('zcount', queue:prefix('locks'), now, math.huge)
    end, length = function(now)
      -- If a 'now' is provided, we're interested in how many are before
      -- that time
      if now then
        return redis.call('zcount', queue:prefix('locks'), 0, now)
      else
        return redis.call('zcard', queue:prefix('locks'))
      end
    end
  }

  -- Access to our dependent jobs
  queue.depends = {
    peek = function(now, offset, count)
      return redis.call('zrange',
        queue:prefix('depends'), offset, offset + count - 1)
    end, add = function(now, jid)
      redis.call('zadd', queue:prefix('depends'), now, jid)
    end, remove = function(...)
      if #arg > 0 then
        return redis.call('zrem', queue:prefix('depends'), unpack(arg))
      end
    end, length = function()
      return redis.call('zcard', queue:prefix('depends'))
    end
  }


  -- Access to the queue level throttled jobs.
  queue.throttled = {
    length = function()
      return (redis.call('zcard', queue:prefix('throttled')) or 0)
    end, peek = function(now, offset, count)
      return redis.call('zrange', queue:prefix('throttled'), offset, offset + count - 1)
    end, add = function(...)
      if #arg > 0 then
        redis.call('zadd', queue:prefix('throttled'), unpack(arg))
      end
    end, remove = function(...)
      if #arg > 0 then
        return redis.call('zrem', queue:prefix('throttled'), unpack(arg))
      end
    end, pop = function(min, max)
      return redis.call('zremrangebyrank', queue:prefix('throttled'), min, max)
    end
  }

  -- Access to our scheduled jobs
  queue.scheduled = {
    peek = function(now, offset, count)
      return redis.call('zrange',
        queue:prefix('scheduled'), offset, offset + count - 1)
    end, ready = function(now, offset, count)
      return redis.call('zrangebyscore',
        queue:prefix('scheduled'), 0, now, 'LIMIT', offset, count)
    end, add = function(when, jid)
      redis.call('zadd', queue:prefix('scheduled'), when, jid)
    end, remove = function(...)
      if #arg > 0 then
        return redis.call('zrem', queue:prefix('scheduled'), unpack(arg))
      end
    end, length = function()
      return redis.call('zcard', queue:prefix('scheduled'))
    end
  }

  -- Access to our recurring jobs
  queue.recurring = {
    peek = function(now, offset, count)
      return redis.call('zrangebyscore', queue:prefix('recur'),
        0, now, 'LIMIT', offset, count)
    end, ready = function(now, offset, count)
    end, add = function(when, jid)
      redis.call('zadd', queue:prefix('recur'), when, jid)
    end, remove = function(...)
      if #arg > 0 then
        return redis.call('zrem', queue:prefix('recur'), unpack(arg))
      end
    end, update = function(increment, jid)
      redis.call('zincrby', queue:prefix('recur'), increment, jid)
    end, score = function(jid)
      return redis.call('zscore', queue:prefix('recur'), jid)
    end, length = function()
      return redis.call('zcard', queue:prefix('recur'))
    end
  }
  return queue
end

-- Return the prefix for this particular queue
function ReqlessQueue:prefix(group)
  if group then
    return ReqlessQueue.ns .. self.name .. '-' .. group
  end

  return ReqlessQueue.ns .. self.name
end

-- Stats(now, date)
-- ---------------------
-- Return the current statistics for a given queue on a given date. The
-- results are returned are a JSON blob:
--
--
--  {
--      # These are unimplemented as of yet
--      'failed': 3,
--      'retries': 5,
--      'wait' : {
--          'total'    : ...,
--          'mean'     : ...,
--          'variance' : ...,
--          'histogram': [
--              ...
--          ]
--      }, 'run': {
--          'total'    : ...,
--          'mean'     : ...,
--          'variance' : ...,
--          'histogram': [
--              ...
--          ]
--      }
--  }
--
-- The histogram's data points are at the second resolution for the first
-- minute, the minute resolution for the first hour, the 15-minute resolution
-- for the first day, the hour resolution for the first 3 days, and then at
-- the day resolution from there on out. The `histogram` key is a list of
-- those values.
function ReqlessQueue:stats(now, date)
  date = assert(tonumber(date),
    'Stats(): Arg "date" missing or not a number: ' .. (date or 'nil'))

  -- The bin is midnight of the provided day
  -- 24 * 60 * 60 = 86400
  local bin = date - (date % 86400)

  -- This a table of all the keys we want to use in order to produce a histogram
  local histokeys = {
    's0','s1','s2','s3','s4','s5','s6','s7','s8','s9','s10','s11','s12','s13','s14','s15','s16','s17','s18','s19','s20','s21','s22','s23','s24','s25','s26','s27','s28','s29','s30','s31','s32','s33','s34','s35','s36','s37','s38','s39','s40','s41','s42','s43','s44','s45','s46','s47','s48','s49','s50','s51','s52','s53','s54','s55','s56','s57','s58','s59',
    'm1','m2','m3','m4','m5','m6','m7','m8','m9','m10','m11','m12','m13','m14','m15','m16','m17','m18','m19','m20','m21','m22','m23','m24','m25','m26','m27','m28','m29','m30','m31','m32','m33','m34','m35','m36','m37','m38','m39','m40','m41','m42','m43','m44','m45','m46','m47','m48','m49','m50','m51','m52','m53','m54','m55','m56','m57','m58','m59',
    'h1','h2','h3','h4','h5','h6','h7','h8','h9','h10','h11','h12','h13','h14','h15','h16','h17','h18','h19','h20','h21','h22','h23',
    'd1','d2','d3','d4','d5','d6'
  }

  local mkstats = function(name, bin, queue)
    -- The results we'll be sending back
    local results = {}

    local key = 'ql:s:' .. name .. ':' .. bin .. ':' .. queue
    local count, mean, vk = unpack(redis.call('hmget', key, 'total', 'mean', 'vk'))

    count = tonumber(count) or 0
    mean  = tonumber(mean) or 0
    vk    = tonumber(vk)

    results.count     = count or 0
    results.mean      = mean  or 0
    results.histogram = {}

    if not count then
      results.std = 0
    else
      if count > 1 then
        results.std = math.sqrt(vk / (count - 1))
      else
        results.std = 0
      end
    end

    local histogram = redis.call('hmget', key, unpack(histokeys))
    for i=1, #histokeys do
      table.insert(results.histogram, tonumber(histogram[i]) or 0)
    end
    return results
  end

  local retries, failed, failures = unpack(redis.call('hmget', 'ql:s:stats:' .. bin .. ':' .. self.name, 'retries', 'failed', 'failures'))
  return {
    retries  = tonumber(retries  or 0),
    failed   = tonumber(failed   or 0),
    failures = tonumber(failures or 0),
    wait     = mkstats('wait', bin, self.name),
    run      = mkstats('run' , bin, self.name)
  }
end

-- Peek
-------
-- Examine the next jobs that would be popped from the queue without actually
-- popping them.
function ReqlessQueue:peek(now, offset, count)
  offset = assert(tonumber(offset),
    'Peek(): Arg "offset" missing or not a number: ' .. tostring(offset))

  count = assert(tonumber(count),
    'Peek(): Arg "count" missing or not a number: ' .. tostring(count))

  if count <= 0 then
    return {}
  end

  local count_with_offset = offset + count

  -- These are the ids that we're going to return. We'll begin with any jobs
  -- that have lost their locks
  local jids = self.locks.expired(now, 0, count_with_offset)

  -- Since we can't just peek the range we want, we have to consider all offset
  -- + count jobs before we can take the relevant range.
  local remaining_capacity = count_with_offset - #jids

  -- If we still need jobs in order to meet demand, then we should
  -- look for all the recurring jobs that need jobs run
  self:check_recurring(now, remaining_capacity)

  -- Now we've checked __all__ the locks for this queue the could
  -- have expired, and are no more than the number requested. If
  -- we still need values in order to meet the demand, then we
  -- should check if any scheduled items, and if so, we should
  -- insert them to ensure correctness when pulling off the next
  -- unit of work.
  self:check_scheduled(now, remaining_capacity)

  if offset > #jids then
    -- Offset takes us past the expired jids, so just return straight from the
    -- work queue
    return self.work.peek(offset - #jids, count)
  end

  -- Return a mix of expired jids and prioritized items from the work queue
  table_extend(jids, self.work.peek(0, remaining_capacity))

  if #jids < offset then
    return {}
  end

  return {unpack(jids, offset + 1, count_with_offset)}
end

-- Return true if this queue is paused
function ReqlessQueue:paused()
  return redis.call('sismember', 'ql:paused_queues', self.name) == 1
end

-- Pause this queue
--
-- Note: long term, we have discussed adding a rate-limiting
-- feature to reqless-core, which would be more flexible and
-- could be used for pausing (i.e. pause = set the rate to 0).
-- For now, this is far simpler, but we should rewrite this
-- in terms of the rate limiting feature if/when that is added.
function ReqlessQueue.pause(now, ...)
  redis.call('sadd', 'ql:paused_queues', unpack(arg))
end

-- Unpause this queue
function ReqlessQueue.unpause(...)
  redis.call('srem', 'ql:paused_queues', unpack(arg))
end

-- Checks for expired locks, scheduled and recurring jobs, returning any
-- jobs that are ready to be processes
function ReqlessQueue:pop(now, worker, count)
  assert(worker, 'Pop(): Arg "worker" missing')
  count = assert(tonumber(count),
    'Pop(): Arg "count" missing or not a number: ' .. tostring(count))

  -- If this queue is paused, then return no jobs
  if self:paused() then
    return {}
  end

  -- Make sure we this worker to the list of seen workers
  redis.call('zadd', 'ql:workers', now, worker)

  local dead_jids = self:invalidate_locks(now, count) or {}
  local popped = {}

  for _, jid in ipairs(dead_jids) do
    local success = self:pop_job(now, worker, Reqless.job(jid))
    -- only track jid if a job was popped and it's not a phantom jid
    if success then
      table.insert(popped, jid)
    end
  end

  -- if queue is at max capacity don't pop any further jobs.
  if not Reqless.throttle(ReqlessQueue.ns .. self.name):available() then
    return popped
  end

  -- Now we've checked __all__ the locks for this queue the could
  -- have expired, and are no more than the number requested.

  -- If we still need jobs in order to meet demand, then we should
  -- look for all the recurring jobs that need jobs run
  self:check_recurring(now, count - #dead_jids)

  -- If we still need values in order to meet the demand, then we
  -- should check if any scheduled items, and if so, we should
  -- insert them to ensure correctness when pulling off the next
  -- unit of work.
  self:check_scheduled(now, count - #dead_jids)

  -- With these in place, we can expand this list of jids based on the work
  -- queue itself and the priorities therein

  -- Since throttles could prevent work queue items from being popped, we can
  -- retry a number of times till we find work items that are not throttled
  local pop_retry_limit = tonumber(
    Reqless.config.get(self.name .. '-max-pop-retry') or
    Reqless.config.get('max-pop-retry', 1)
  )

  -- Keep trying to fulfill fulfill jobs from the work queue until we reach
  -- the desired count or exhaust our retry limit
  while #popped < count and pop_retry_limit > 0 do

    local jids = self.work.peek(0, count - #popped) or {}

    -- If there is nothing in the work queue, then no need to keep looping
    if #jids == 0 then
      break
    end


    for _, jid in ipairs(jids) do
      local job = Reqless.job(jid)
      if job:throttles_acquire(now) then
        local success = self:pop_job(now, worker, job)
        -- only track jid if a job was popped and it's not a phantom jid
        if success then
          table.insert(popped, jid)
        end
      else
        self:throttle(now, job)
      end
    end

    -- All jobs should have acquired locks or be throttled,
    -- ergo, remove all jids from work queue
    self.work.remove(unpack(jids))

    pop_retry_limit = pop_retry_limit - 1
  end

  return popped
end

-- Throttle a job
function ReqlessQueue:throttle(now, job)
  job:throttle(now)
  self.throttled.add(now, job.jid)
  local state = unpack(job:data('state'))
  if state ~= 'throttled' then
    job:update({state = 'throttled'})
    job:history(now, 'throttled', {queue = self.name})
  end
end

function ReqlessQueue:pop_job(now, worker, job)
  local state
  local jid = job.jid
  local job_state = job:data('state')
  -- if the job doesn't exist, short circuit
  if not job_state then
    return false
  end

  state = unpack(job_state)
  job:history(now, 'popped', {worker = worker})

  -- We should find the heartbeat interval for this queue heartbeat
  local expires = now + tonumber(
    Reqless.config.get(self.name .. '-heartbeat') or
    Reqless.config.get('heartbeat', 60))

  -- Update the wait time statistics
  -- Just does job:data('time') do the same as this?
  local time = tonumber(redis.call('hget', ReqlessJob.ns .. jid, 'time') or now)
  local waiting = now - time
  self:stat(now, 'wait', waiting)
  redis.call('hset', ReqlessJob.ns .. jid,
    'time', string.format("%.20f", now))

  -- Add this job to the list of jobs handled by this worker
  redis.call('zadd', 'ql:w:' .. worker .. ':jobs', expires, jid)

  -- Update the jobs data, and add its locks, and return the job
  job:update({
    worker  = worker,
    expires = expires,
    state   = 'running'
  })

  self.locks.add(expires, jid)

  local tracked = redis.call('zscore', 'ql:tracked', jid) ~= false
  if tracked then
    Reqless.publish('popped', jid)
  end
  return true
end

-- Update the stats for this queue
function ReqlessQueue:stat(now, stat, val)
  -- The bin is midnight of the provided day
  local bin = now - (now % 86400)
  local key = 'ql:s:' .. stat .. ':' .. bin .. ':' .. self.name

  -- Get the current data
  local count, mean, vk = unpack(
    redis.call('hmget', key, 'total', 'mean', 'vk'))

  -- If there isn't any data there presently, then we must initialize it
  count = count or 0
  if count == 0 then
    mean  = val
    vk    = 0
    count = 1
  else
    count = count + 1
    local oldmean = mean
    mean  = mean + (val - mean) / count
    vk    = vk + (val - mean) * (val - oldmean)
  end

  -- Now, update the histogram
  -- - `s1`, `s2`, ..., -- second-resolution histogram counts
  -- - `m1`, `m2`, ..., -- minute-resolution
  -- - `h1`, `h2`, ..., -- hour-resolution
  -- - `d1`, `d2`, ..., -- day-resolution
  val = math.floor(val)
  if val < 60 then -- seconds
    redis.call('hincrby', key, 's' .. val, 1)
  elseif val < 3600 then -- minutes
    redis.call('hincrby', key, 'm' .. math.floor(val / 60), 1)
  elseif val < 86400 then -- hours
    redis.call('hincrby', key, 'h' .. math.floor(val / 3600), 1)
  else -- days
    redis.call('hincrby', key, 'd' .. math.floor(val / 86400), 1)
  end
  redis.call('hmset', key, 'total', count, 'mean', mean, 'vk', vk)
end

-- Put(now, jid, klass, data, delay,
--     [priority, p],
--     [tags, t],
--     [retries, r],
--     [depends, '[...]'])
-- -----------------------
-- Insert a job into the queue with the given priority, tags, delay, klass and
-- data.
function ReqlessQueue:put(now, worker, jid, klass, raw_data, delay, ...)
  assert(jid  , 'Put(): Arg "jid" missing')
  assert(klass, 'Put(): Arg "klass" missing')
  local data = assert(cjson.decode(raw_data),
    'Put(): Arg "data" missing or not JSON: ' .. tostring(raw_data))
  delay = assert(tonumber(delay),
    'Put(): Arg "delay" not a number: ' .. tostring(delay))

  -- Read in all the optional parameters. All of these must come in pairs, so
  -- if we have an odd number of extra args, raise an error
  if #arg % 2 == 1 then
    error('Odd number of additional args: ' .. tostring(arg))
  end
  local options = {}
  for i = 1, #arg, 2 do options[arg[i]] = arg[i + 1] end

  -- Let's see what the old priority and tags were
  local job = Reqless.job(jid)
  local priority, tags, oldqueue, state, failure, retries, oldworker =
    unpack(redis.call('hmget', ReqlessJob.ns .. jid, 'priority', 'tags',
      'queue', 'state', 'failure', 'retries', 'worker'))

  -- If there are old tags, then we should remove the tags this job has
  if tags then
    Reqless.tag(now, 'remove', jid, unpack(cjson.decode(tags)))
  end

  -- Sanity check on optional args
  local retries  = assert(tonumber(options['retries']  or retries or 5) ,
    'Put(): Arg "retries" not a number: ' .. tostring(options['retries']))
  local tags     = assert(cjson.decode(options['tags'] or tags or '[]' ),
    'Put(): Arg "tags" not JSON'          .. tostring(options['tags']))
  local priority = assert(tonumber(options['priority'] or priority or 0),
    'Put(): Arg "priority" not a number'  .. tostring(options['priority']))
  local depends = assert(cjson.decode(options['depends'] or '[]') ,
    'Put(): Arg "depends" not JSON: '     .. tostring(options['depends']))
  local throttles = assert(cjson.decode(options['throttles'] or '[]'),
    'Put(): Arg "throttles" not JSON array: ' .. tostring(options['throttles']))

  -- If the job has old dependencies, determine which dependencies are
  -- in the new dependencies but not in the old ones, and which are in the
  -- old ones but not in the new
  if #depends > 0 then
    -- This makes it easier to check if it's in the new list
    local new = {}
    for _, d in ipairs(depends) do new[d] = 1 end

    -- Now find what's in the original, but not the new
    local original = redis.call(
      'smembers', ReqlessJob.ns .. jid .. '-dependencies')
    for _, dep in pairs(original) do
      if new[dep] == nil then
        -- Remove k as a dependency
        redis.call('srem', ReqlessJob.ns .. dep .. '-dependents'  , jid)
        redis.call('srem', ReqlessJob.ns .. jid .. '-dependencies', dep)
      end
    end
  end

  -- Send out a log message
  Reqless.publish('log', cjson.encode({
    jid   = jid,
    event = 'put',
    queue = self.name
  }))

  -- Update the history to include this new change
  job:history(now, 'put', {queue = self.name})

  -- If this item was previously in another queue, then we should remove it from there
  -- and remove the associated throttle
  if oldqueue then
    local queue_obj = Reqless.queue(oldqueue)
    queue_obj:remove_job(jid)
    local old_qid = ReqlessQueue.ns .. oldqueue
    for index, throttle_name in ipairs(throttles) do
      if throttle_name == old_qid then
        table.remove(throttles, index)
      end
    end
  end

  -- If this had previously been given out to a worker, make sure to remove it
  -- from that worker's jobs
  if oldworker and oldworker ~= '' then
    redis.call('zrem', 'ql:w:' .. oldworker .. ':jobs', jid)
    -- If it's a different worker that's putting this job, send a notification
    -- to the last owner of the job
    if oldworker ~= worker then
      -- We need to inform whatever worker had that job
      local encoded = cjson.encode({
        jid    = jid,
        event  = 'lock_lost',
        worker = oldworker
      })
      Reqless.publish('w:' .. oldworker, encoded)
      Reqless.publish('log', encoded)
    end
  end

  -- If the job was previously in the 'completed' state, then we should
  -- remove it from being enqueued for destructination
  if state == 'complete' then
    redis.call('zrem', 'ql:completed', jid)
  end

  -- Add this job to the list of jobs tagged with whatever tags were supplied
  for _, tag in ipairs(tags) do
    Reqless.job(jid):insert_tag(now, tag)
  end

  -- If we're in the failed state, remove all of our data
  if state == 'failed' then
    failure = cjson.decode(failure)
    -- We need to make this remove it from the failed queues
    redis.call('lrem', 'ql:f:' .. failure.group, 0, jid)
    if redis.call('llen', 'ql:f:' .. failure.group) == 0 then
      redis.call('srem', 'ql:failures', failure.group)
    end
    -- The bin is midnight of the provided day
    -- 24 * 60 * 60 = 86400
    local bin = failure.when - (failure.when % 86400)
    -- We also need to decrement the stats about the queue on
    -- the day that this failure actually happened.
    redis.call('hincrby', 'ql:s:stats:' .. bin .. ':' .. self.name, 'failed'  , -1)
  end

  -- insert default queue throttle
  table.insert(throttles, ReqlessQueue.ns .. self.name)

  data = {
    'jid'      , jid,
    'klass'    , klass,
    'data'     , raw_data,
    'priority' , priority,
    'tags'     , cjson.encode(tags),
    'state'    , ((delay > 0) and 'scheduled') or 'waiting',
    'worker'   , '',
    'expires'  , 0,
    'queue'    , self.name,
    'retries'  , retries,
    'remaining', retries,
    'time'     , string.format("%.20f", now),
    'throttles', cjson.encode(throttles)
  }

  -- First, let's save its data
  redis.call('hmset', ReqlessJob.ns .. jid, unpack(data))

  -- These are the jids we legitimately have to wait on
  for _, j in ipairs(depends) do
    -- Make sure it's something other than 'nil' or complete.
    local state = redis.call('hget', ReqlessJob.ns .. j, 'state')
    if (state and state ~= 'complete') then
      redis.call('sadd', ReqlessJob.ns .. j .. '-dependents'  , jid)
      redis.call('sadd', ReqlessJob.ns .. jid .. '-dependencies', j)
    end
  end

  -- Now, if a delay was provided, and if it's in the future,
  -- then we'll have to schedule it. Otherwise, we're just
  -- going to add it to the work queue.
  if delay > 0 then
    if redis.call('scard', ReqlessJob.ns .. jid .. '-dependencies') > 0 then
      -- We've already put it in 'depends'. Now, we must just save the data
      -- for when it's scheduled
      self.depends.add(now, jid)
      redis.call('hmset', ReqlessJob.ns .. jid,
        'state', 'depends',
        'scheduled', now + delay)
    else
      self.scheduled.add(now + delay, jid)
    end
  else
    -- to avoid false negatives when popping jobs check if the job should be
    -- throttled immediately.
    local job = Reqless.job(jid)
    if redis.call('scard', ReqlessJob.ns .. jid .. '-dependencies') > 0 then
      self.depends.add(now, jid)
      redis.call('hset', ReqlessJob.ns .. jid, 'state', 'depends')
    elseif not job:throttles_available() then
      self:throttle(now, job)
    else
      self.work.add(now, priority, jid)
    end
  end

  -- Lastly, we're going to make sure that this item is in the
  -- set of known queues. We should keep this sorted by the
  -- order in which we saw each of these queues
  if redis.call('zscore', 'ql:queues', self.name) == false then
    redis.call('zadd', 'ql:queues', now, self.name)
  end

  if redis.call('zscore', 'ql:tracked', jid) ~= false then
    Reqless.publish('put', jid)
  end

  return jid
end

-- Move `count` jobs out of the failed state and into this queue
function ReqlessQueue:unfail(now, group, count)
  assert(group, 'Unfail(): Arg "group" missing')
  count = assert(tonumber(count or 25),
    'Unfail(): Arg "count" not a number: ' .. tostring(count))

  -- Get up to that many jobs, and we'll put them in the appropriate queue
  local jids = redis.call('lrange', 'ql:f:' .. group, -count, -1)

  -- And now set each job's state, and put it into the appropriate queue
  local toinsert = {}
  for _, jid in ipairs(jids) do
    local job = Reqless.job(jid)
    local data = job:data()
    job:history(now, 'put', {queue = self.name})
    redis.call('hmset', ReqlessJob.ns .. data.jid,
      'state'    , 'waiting',
      'worker'   , '',
      'expires'  , 0,
      'queue'    , self.name,
      'remaining', data.retries or 5)
    self.work.add(now, data.priority, data.jid)
  end

  -- Remove these jobs from the failed state
  redis.call('ltrim', 'ql:f:' .. group, 0, -count - 1)
  if (redis.call('llen', 'ql:f:' .. group) == 0) then
    redis.call('srem', 'ql:failures', group)
  end

  return #jids
end

-- Recur a job of type klass in this queue
function ReqlessQueue:recur(now, jid, klass, raw_data, spec, ...)
  assert(jid  , 'RecurringJob On(): Arg "jid" missing')
  assert(klass, 'RecurringJob On(): Arg "klass" missing')
  assert(spec , 'RecurringJob On(): Arg "spec" missing')
  local data = assert(cjson.decode(raw_data),
    'RecurringJob On(): Arg "data" not JSON: ' .. tostring(raw_data))

  -- At some point in the future, we may have different types of recurring
  -- jobs, but for the time being, we only have 'interval'-type jobs
  if spec == 'interval' then
    local interval = assert(tonumber(arg[1]),
      'Recur(): Arg "interval" not a number: ' .. tostring(arg[1]))
    local offset   = assert(tonumber(arg[2]),
      'Recur(): Arg "offset" not a number: '   .. tostring(arg[2]))
    if interval <= 0 then
      error('Recur(): Arg "interval" must be greater than 0')
    end

    -- Read in all the optional parameters. All of these must come in
    -- pairs, so if we have an odd number of extra args, raise an error
    if #arg % 2 == 1 then
      error('Odd number of additional args: ' .. tostring(arg))
    end

    -- Read in all the optional parameters
    local options = {}
    for i = 3, #arg, 2 do options[arg[i]] = arg[i + 1] end
    options.tags = assert(cjson.decode(options.tags or '{}'),
      'Recur(): Arg "tags" must be JSON string array: ' .. tostring(
        options.tags))
    options.priority = assert(tonumber(options.priority or 0),
      'Recur(): Arg "priority" not a number: ' .. tostring(
        options.priority))
    options.retries = assert(tonumber(options.retries  or 0),
      'Recur(): Arg "retries" not a number: ' .. tostring(
        options.retries))
    options.backlog = assert(tonumber(options.backlog  or 0),
      'Recur(): Arg "backlog" not a number: ' .. tostring(
        options.backlog))
    options.throttles = assert(cjson.decode(options['throttles'] or '{}'),
      'Recur(): Arg "throttles" not JSON array: ' .. tostring(options['throttles']))

    local count, old_queue = unpack(redis.call('hmget', 'ql:r:' .. jid, 'count', 'queue'))
    count = count or 0

    local throttles = options['throttles'] or {}

    -- If it has previously been in another queue, then we should remove
    -- some information about it
    if old_queue then
      Reqless.queue(old_queue).recurring.remove(jid)

      for index, throttle_name in ipairs(throttles) do
        if throttle_name == old_queue then
          table.remove(throttles, index)
        end
      end
    end

    -- insert default queue throttle
    table.insert(throttles, ReqlessQueue.ns .. self.name)

    -- Do some insertions
    redis.call('hmset', 'ql:r:' .. jid,
      'jid'      , jid,
      'klass'    , klass,
      'data'     , raw_data,
      'priority' , options.priority,
      'tags'     , cjson.encode(options.tags or {}),
      'state'    , 'recur',
      'queue'    , self.name,
      'type'     , 'interval',
      -- How many jobs we've spawned from this
      'count'    , count,
      'interval' , interval,
      'retries'  , options.retries,
      'backlog'  , options.backlog,
      'throttles', cjson.encode(throttles))
    -- Now, we should schedule the next run of the job
    self.recurring.add(now + offset, jid)

    -- Lastly, we're going to make sure that this item is in the
    -- set of known queues. We should keep this sorted by the
    -- order in which we saw each of these queues
    if redis.call('zscore', 'ql:queues', self.name) == false then
      redis.call('zadd', 'ql:queues', now, self.name)
    end

    return jid
  end

  error('Recur(): schedule type "' .. tostring(spec) .. '" unknown')
end

-- Return the length of the queue
function ReqlessQueue:length()
  return  self.locks.length() + self.work.length() + self.scheduled.length()
end

-------------------------------------------------------------------------------
-- Housekeeping methods
-------------------------------------------------------------------------------
function ReqlessQueue:remove_job(jid)
  self.work.remove(jid)
  self.locks.remove(jid)
  self.throttled.remove(jid)
  self.depends.remove(jid)
  self.scheduled.remove(jid)
end

-- Instantiate any recurring jobs that are ready
function ReqlessQueue:check_recurring(now, count)
  if count <= 0 then
    return
  end
  -- This is how many jobs we've moved so far
  local moved = 0
  -- These are the recurring jobs that need work
  local r = self.recurring.peek(now, 0, count)
  for _, jid in ipairs(r) do
    -- For each of the jids that need jobs scheduled, first
    -- get the last time each of them was run, and then increment
    -- it by its interval. While this time is less than now,
    -- we need to keep putting jobs on the queue
    local r = redis.call('hmget', 'ql:r:' .. jid, 'klass', 'data', 'priority',
        'tags', 'retries', 'interval', 'backlog', 'throttles')
    local klass, data, priority, tags, retries, interval, backlog, throttles = unpack(
      redis.call('hmget', 'ql:r:' .. jid, 'klass', 'data', 'priority',
        'tags', 'retries', 'interval', 'backlog', 'throttles'))
    local _tags = cjson.decode(tags)
    local score = math.floor(tonumber(self.recurring.score(jid)))
    interval = tonumber(interval)

    -- If the backlog is set for this job, then see if it's been a long
    -- time since the last pop
    backlog = tonumber(backlog or 0)
    if backlog ~= 0 then
      -- Check how many jobs we could concievably generate
      local num = ((now - score) / interval)
      if num > backlog then
        -- Update the score
        score = score + (
          math.ceil(num - backlog) * interval
        )
      end
    end

    -- We're saving this value so that in the history, we can accurately
    -- reflect when the job would normally have been scheduled
    while (score <= now) and (moved < count) do
      local count = redis.call('hincrby', 'ql:r:' .. jid, 'count', 1)
      moved = moved + 1

      local child_jid = jid .. '-' .. count

      -- Add this job to the list of jobs tagged with whatever tags were
      -- supplied
      for _, tag in ipairs(_tags) do
        Reqless.job(child_jid):insert_tag(now, tag)
      end

      -- First, let's save its data
      redis.call('hmset', ReqlessJob.ns .. child_jid,
        'jid'      , child_jid,
        'klass'    , klass,
        'data'     , data,
        'priority' , priority,
        'tags'     , tags,
        'state'    , 'waiting',
        'worker'   , '',
        'expires'  , 0,
        'queue'    , self.name,
        'retries'  , retries,
        'remaining', retries,
        'time'     , string.format("%.20f", score),
        'throttles', throttles,
        'spawned_from_jid', jid)

      Reqless.job(child_jid):history(score, 'put', {queue = self.name})

      -- Now, if a delay was provided, and if it's in the future,
      -- then we'll have to schedule it. Otherwise, we're just
      -- going to add it to the work queue.
      self.work.add(score, priority, child_jid)

      score = score + interval
      self.recurring.add(score, jid)
    end
  end
end

-- Check for any jobs that have been scheduled, and shovel them onto
-- the work queue. Returns nothing, but afterwards, up to `count`
-- scheduled jobs will be moved into the work queue
function ReqlessQueue:check_scheduled(now, count)
  if count <= 0 then
    return
  end
  -- zadd is a list of arguments that we'll be able to use to
  -- insert into the work queue
  local scheduled = self.scheduled.ready(now, 0, count)
  for _, jid in ipairs(scheduled) do
    -- With these in hand, we'll have to go out and find the
    -- priorities of these jobs, and then we'll insert them
    -- into the work queue and then when that's complete, we'll
    -- remove them from the scheduled queue
    local priority = tonumber(
      redis.call('hget', ReqlessJob.ns .. jid, 'priority') or 0)
    self.work.add(now, priority, jid)
    self.scheduled.remove(jid)

    -- We should also update them to have the state 'waiting'
    -- instead of 'scheduled'
    redis.call('hset', ReqlessJob.ns .. jid, 'state', 'waiting')
  end
end

-- Check for and invalidate any locks that have been lost. Returns the
-- list of jids that have been invalidated
function ReqlessQueue:invalidate_locks(now, count)
  local jids = {}
  -- Iterate through all the expired locks and add them to the list
  -- of keys that we'll return
  for _, jid in ipairs(self.locks.expired(now, 0, count)) do
    -- Remove this job from the jobs that the worker that was running it
    -- has
    local worker, failure = unpack(
      redis.call('hmget', ReqlessJob.ns .. jid, 'worker', 'failure'))
    redis.call('zrem', 'ql:w:' .. worker .. ':jobs', jid)

    -- We'll provide a grace period after jobs time out for them to give
    -- some indication of the failure mode. After that time, however, we'll
    -- consider the worker dust in the wind
    local grace_period = tonumber(Reqless.config.get('grace-period'))

    -- Whether or not we've already sent a coutesy message
    local courtesy_sent = tonumber(
      redis.call('hget', ReqlessJob.ns .. jid, 'grace') or 0)

    -- If the remaining value is an odd multiple of 0.5, then we'll assume
    -- that we're just sending the message. Otherwise, it's time to
    -- actually hand out the work to another worker
    local send_message = (courtesy_sent ~= 1)
    local invalidate   = not send_message

    -- If the grace period has been disabled, then we'll do both.
    if grace_period <= 0 then
      send_message = true
      invalidate   = true
    end

    if send_message then
      -- This is where we supply a courtesy message and give the worker
      -- time to provide a failure message
      if redis.call('zscore', 'ql:tracked', jid) ~= false then
        Reqless.publish('stalled', jid)
      end
      Reqless.job(jid):history(now, 'timed-out')
      redis.call('hset', ReqlessJob.ns .. jid, 'grace', 1)

      -- Send a message to let the worker know that its lost its lock on
      -- the job
      local encoded = cjson.encode({
        jid    = jid,
        event  = 'lock_lost',
        worker = worker,
      })
      Reqless.publish('w:' .. worker, encoded)
      Reqless.publish('log', encoded)
      self.locks.add(now + grace_period, jid)

      -- If we got any expired locks, then we should increment the
      -- number of retries for this stage for this bin. The bin is
      -- midnight of the provided day
      local bin = now - (now % 86400)
      redis.call('hincrby',
        'ql:s:stats:' .. bin .. ':' .. self.name, 'retries', 1)
    end

    if invalidate then
      -- Unset the grace period attribute so that next time we'll send
      -- the grace period
      redis.call('hdel', ReqlessJob.ns .. jid, 'grace', 0)

      -- See how many remaining retries the job has
      local remaining = tonumber(redis.call(
        'hincrby', ReqlessJob.ns .. jid, 'remaining', -1))

      -- This is where we actually have to time out the work
      if remaining < 0 then
        -- Now remove the instance from the schedule, and work queues
        -- for the queue it's in
        self.work.remove(jid)
        self.locks.remove(jid)
        self.scheduled.remove(jid)

        local job = Reqless.job(jid)
        local job_data = Reqless.job(jid):data()
        local queue = job_data['queue']
        local group = 'failed-retries-' .. queue

        job:throttles_release(now)

        job:history(now, 'failed', {group = group})
        redis.call('hmset', ReqlessJob.ns .. jid, 'state', 'failed',
          'worker', '',
          'expires', '')
        -- If the failure has not already been set, then set it
        redis.call('hset', ReqlessJob.ns .. jid,
        'failure', cjson.encode({
          group   = group,
          message = 'Job exhausted retries in queue "' .. self.name .. '"',
          when    = now,
          worker  = unpack(job:data('worker'))
        }))

        -- Add this type of failure to the list of failures
        redis.call('sadd', 'ql:failures', group)
        -- And add this particular instance to the failed types
        redis.call('lpush', 'ql:f:' .. group, jid)

        if redis.call('zscore', 'ql:tracked', jid) ~= false then
          Reqless.publish('failed', jid)
        end
        Reqless.publish('log', cjson.encode({
          jid     = jid,
          event   = 'failed',
          group   = group,
          worker  = worker,
          message =
            'Job exhausted retries in queue "' .. self.name .. '"'
        }))

        -- Increment the count of the failed jobs
        local bin = now - (now % 86400)
        redis.call('hincrby',
          'ql:s:stats:' .. bin .. ':' .. self.name, 'failures', 1)
        redis.call('hincrby',
          'ql:s:stats:' .. bin .. ':' .. self.name, 'failed'  , 1)
      else
        table.insert(jids, jid)
      end
    end
  end

  return jids
end

-- Forget the provided queues. As in, remove them from the list of known queues
function ReqlessQueue.deregister(...)
  redis.call('zrem', Reqless.ns .. 'queues', unpack(arg))
end

-- Return information about a particular queue, or all queues
--  [
--      {
--          'name': 'testing',
--          'stalled': 2,
--          'waiting': 5,
--          'running': 5,
--          'scheduled': 10,
--          'depends': 5,
--          'recurring': 0
--      }, {
--          ...
--      }
--  ]
function ReqlessQueue.counts(now, name)
  if name then
    local queue = Reqless.queue(name)
    local stalled = queue.locks.length(now)
    -- Check for any scheduled jobs that need to be moved
    queue:check_scheduled(now, queue.scheduled.length())
    return {
      name      = name,
      waiting   = queue.work.length(),
      stalled   = stalled,
      running   = queue.locks.length() - stalled,
      throttled = queue.throttled.length(),
      scheduled = queue.scheduled.length(),
      depends   = queue.depends.length(),
      recurring = queue.recurring.length(),
      paused    = queue:paused()
    }
  end

  local queues = redis.call('zrange', 'ql:queues', 0, -1)
  local response = {}
  for _, qname in ipairs(queues) do
    table.insert(response, ReqlessQueue.counts(now, qname))
  end
  return response
end
-- Get all the attributes of this particular job
function ReqlessRecurringJob:data()
  local job = redis.call(
    'hmget', 'ql:r:' .. self.jid, 'jid', 'klass', 'state', 'queue',
    'priority', 'interval', 'retries', 'count', 'data', 'tags', 'backlog', 'throttles')

  if not job[1] then
    return nil
  end

  return {
    jid          = job[1],
    klass        = job[2],
    state        = job[3],
    queue        = job[4],
    priority     = tonumber(job[5]),
    interval     = tonumber(job[6]),
    retries      = tonumber(job[7]),
    count        = tonumber(job[8]),
    data         = job[9],
    tags         = cjson.decode(job[10]),
    backlog      = tonumber(job[11] or 0),
    throttles    = cjson.decode(job[12] or '[]'),
  }
end

-- Update the recurring job data. Key can be:
--      - priority
--      - interval
--      - retries
--      - data
--      - klass
--      - queue
--      - backlog
function ReqlessRecurringJob:update(now, ...)
  local options = {}
  -- Make sure that the job exists
  if redis.call('exists', 'ql:r:' .. self.jid) ~= 0 then
    for i = 1, #arg, 2 do
      local key = arg[i]
      local value = arg[i+1]
      assert(value, 'No value provided for ' .. tostring(key))
      if key == 'priority' or key == 'interval' or key == 'retries' then
        value = assert(tonumber(value), 'Recur(): Arg "' .. key .. '" must be a number: ' .. tostring(value))
        -- If the command is 'interval', then we need to update the
        -- time when it should next be scheduled
        if key == 'interval' then
          local queue, interval = unpack(redis.call('hmget', 'ql:r:' .. self.jid, 'queue', 'interval'))
          Reqless.queue(queue).recurring.update(
            value - tonumber(interval), self.jid)
        end
        redis.call('hset', 'ql:r:' .. self.jid, key, value)
      elseif key == 'data' then
        assert(cjson.decode(value), 'Recur(): Arg "data" is not JSON-encoded: ' .. tostring(value))
        redis.call('hset', 'ql:r:' .. self.jid, 'data', value)
      elseif key == 'klass' then
        redis.call('hset', 'ql:r:' .. self.jid, 'klass', value)
      elseif key == 'queue' then
        local old_queue_name = redis.call('hget', 'ql:r:' .. self.jid, 'queue')
        local queue_obj = Reqless.queue(old_queue_name)
        local score = queue_obj.recurring.score(self.jid)

        -- Detach from the old queue
        queue_obj.recurring.remove(self.jid)
        local throttles = cjson.decode(redis.call('hget', 'ql:r:' .. self.jid, 'throttles') or '{}')
        for index, throttle_name in ipairs(throttles) do
          if throttle_name == ReqlessQueue.ns .. old_queue_name then
            table.remove(throttles, index)
          end
        end


        -- Attach to the new queue
        table.insert(throttles, ReqlessQueue.ns .. value)
        redis.call('hset', 'ql:r:' .. self.jid, 'throttles', cjson.encode(throttles))

        Reqless.queue(value).recurring.add(score, self.jid)
        redis.call('hset', 'ql:r:' .. self.jid, 'queue', value)
        -- If we don't already know about the queue, learn about it
        if redis.call('zscore', 'ql:queues', value) == false then
          redis.call('zadd', 'ql:queues', now, value)
        end
      elseif key == 'backlog' then
        value = assert(tonumber(value),
          'Recur(): Arg "backlog" not a number: ' .. tostring(value))
        redis.call('hset', 'ql:r:' .. self.jid, 'backlog', value)
      elseif key == 'throttles' then
        local throttles = assert(cjson.decode(value), 'Recur(): Arg "throttles" is not JSON-encoded: ' .. tostring(value))
        redis.call('hset', 'ql:r:' .. self.jid, 'throttles', cjson.encode(throttles))
      else
        error('Recur(): Unrecognized option "' .. key .. '"')
      end
    end
    return true
  end

  error('Recur(): No recurring job ' .. self.jid)
end

-- Tags this recurring job with the provided tags
function ReqlessRecurringJob:tag(...)
  local tags = redis.call('hget', 'ql:r:' .. self.jid, 'tags')
  -- If the job has been canceled / deleted, then return false
  if tags then
    -- Decode the json blob, convert to dictionary
    tags = cjson.decode(tags)
    local _tags = {}
    for _, v in ipairs(tags) do _tags[v] = true end

    -- Otherwise, add the job to the sorted set with that tags
    for i=1, #arg do if _tags[arg[i]] == nil then table.insert(tags, arg[i]) end end

    tags = cjson.encode(tags)
    redis.call('hset', 'ql:r:' .. self.jid, 'tags', tags)
    return tags
  end

  error('Tag(): Job ' .. self.jid .. ' does not exist')
end

-- Removes a tag from the recurring job
function ReqlessRecurringJob:untag(...)
  -- Get the existing tags
  local tags = redis.call('hget', 'ql:r:' .. self.jid, 'tags')
  -- If the job has been canceled / deleted, then return false
  if tags then
    -- Decode the json blob, convert to dictionary
    tags = cjson.decode(tags)
    local _tags = {}
    -- Make a hash
    for _, v in ipairs(tags) do _tags[v] = true end
    -- Delete these from the hash
    for i = 1, #arg do _tags[arg[i]] = nil end
    -- Back into a list
    local results = {}
    for _, tag in ipairs(tags) do if _tags[tag] then table.insert(results, tag) end end
    -- json encode them, set, and return
    tags = cjson.encode(results)
    redis.call('hset', 'ql:r:' .. self.jid, 'tags', tags)
    return tags
  end

  error('Untag(): Job ' .. self.jid .. ' does not exist')
end

-- Stop further occurrences of this job
function ReqlessRecurringJob:unrecur()
  -- First, find out what queue it was attached to
  local queue = redis.call('hget', 'ql:r:' .. self.jid, 'queue')
  if queue then
    -- Now, delete it from the queue it was attached to, and delete the
    -- thing itself
    Reqless.queue(queue).recurring.remove(self.jid)
    redis.call('del', 'ql:r:' .. self.jid)
    return true
  end

  return true
end
-- Deregisters these workers from the list of known workers
function ReqlessWorker.deregister(...)
  redis.call('zrem', 'ql:workers', unpack(arg))
end

-- Provide data about all the workers, or if a specific worker is provided,
-- then which jobs that worker is responsible for. If no worker is provided,
-- expect a response of the form:
--
--  [
--      # This is sorted by the recency of activity from that worker
--      {
--          'name'   : 'hostname1-pid1',
--          'jobs'   : 20,
--          'stalled': 0
--      }, {
--          ...
--      }
--  ]
--
-- If a worker id is provided, then expect a response of the form:
--
--  {
--      'jobs': [
--          jid1,
--          jid2,
--          ...
--      ], 'stalled': [
--          jid1,
--          ...
--      ]
--  }
--
function ReqlessWorker.counts(now, worker)
  -- Clean up all the workers' job lists if they're too old. This is
  -- determined by the `max-worker-age` configuration, defaulting to the
  -- last day. Seems like a 'reasonable' default
  local interval = tonumber(Reqless.config.get('max-worker-age', 86400))

  local workers  = redis.call('zrangebyscore', 'ql:workers', 0, now - interval)
  for _, worker in ipairs(workers) do
    redis.call('del', 'ql:w:' .. worker .. ':jobs')
  end

  -- And now remove them from the list of known workers
  redis.call('zremrangebyscore', 'ql:workers', 0, now - interval)

  if worker then
    return {
      jobs    = redis.call('zrevrangebyscore', 'ql:w:' .. worker .. ':jobs', now + 8640000, now),
      stalled = redis.call('zrevrangebyscore', 'ql:w:' .. worker .. ':jobs', now, 0)
    }
  end

  local response = {}
  local workers = redis.call('zrevrange', 'ql:workers', 0, -1)
  for _, worker in ipairs(workers) do
    table.insert(response, {
      name    = worker,
      jobs    = redis.call('zcount', 'ql:w:' .. worker .. ':jobs', now, now + 8640000),
      stalled = redis.call('zcount', 'ql:w:' .. worker .. ':jobs', 0, now)
    })
  end
  return response
end
-- Retrieve the data for a throttled resource
function ReqlessThrottle:data()
  -- Default values for the data
  local data = {
    id = self.id,
    maximum = 0
  }

  -- Retrieve data stored in redis
  local throttle = redis.call('hmget', ReqlessThrottle.ns .. self.id, 'id', 'maximum')

  if throttle[2] then
    data.maximum = tonumber(throttle[2])
  end

  return data
end

-- Set the data for a throttled resource
function ReqlessThrottle:set(data, expiration)
  redis.call('hmset', ReqlessThrottle.ns .. self.id, 'id', self.id, 'maximum', data.maximum)
  if expiration > 0 then
    redis.call('expire', ReqlessThrottle.ns .. self.id, expiration)
  end
end

-- Delete a throttled resource
function ReqlessThrottle:unset()
  redis.call('del', ReqlessThrottle.ns .. self.id)
end

-- Acquire a throttled resource for a job.
-- Returns true of the job acquired the resource, false otherwise
function ReqlessThrottle:acquire(jid)
  if not self:available() then
    return false
  end

  self.locks.add(1, jid)
  return true
end

function ReqlessThrottle:pend(now, jid)
  self.pending.add(now, jid)
end

-- Releases the lock taken by the specified jid.
-- number of jobs released back into the queues is determined by the locks_available method.
function ReqlessThrottle:release(now, jid)
  -- Only attempt to remove from the pending set if the job wasn't found in the
  -- locks set
  if self.locks.remove(jid) == 0 then
    self.pending.remove(jid)
  end

  local available_locks = self:locks_available()
  if self.pending.length() == 0 or available_locks < 1 then
    return
  end

  -- subtract one to ensure we pop the correct amount. peek(0, 0) returns the first element
  -- peek(0,1) return the first two.
  for _, jid in ipairs(self.pending.peek(0, available_locks - 1)) do
    local job = Reqless.job(jid)
    local data = job:data()
    local queue = Reqless.queue(data['queue'])

    queue.throttled.remove(jid)
    queue.work.add(now, data.priority, jid)
  end

  -- subtract one to ensure we pop the correct amount. pop(0, 0) pops the first element
  -- pop(0,1) pops the first two.
  local popped = self.pending.pop(0, available_locks - 1)
end

-- Returns true if the throttle has locks available, false otherwise.
function ReqlessThrottle:available()
  return self.maximum == 0 or self.locks.length() < self.maximum
end

-- Returns the TTL of the throttle
function ReqlessThrottle:ttl()
  return redis.call('ttl', ReqlessThrottle.ns .. self.id)
end

-- Returns the number of locks available for the throttle.
-- calculated by maximum - locks.length(), if the throttle is unlimited
-- then up to 10 jobs are released.
function ReqlessThrottle:locks_available()
  if self.maximum == 0 then
    -- Arbitrarily chosen value. might want to make it configurable in the future.
    return 10
  end

  return self.maximum - self.locks.length()
end
