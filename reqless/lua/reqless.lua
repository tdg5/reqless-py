-- Current SHA: 3ca67635c05ba8754151e2f14869630bb791a1a3
-- This is a generated file
local Reqless = {
  ns = 'rql:'
}

local ReqlessQueue = {
  ns = Reqless.ns .. 'q:'
}
ReqlessQueue.__index = ReqlessQueue

local ReqlessWorker = {
  ns = Reqless.ns .. 'w:'
}
ReqlessWorker.__index = ReqlessWorker

local ReqlessJob = {
  ns = Reqless.ns .. 'j:'
}
ReqlessJob.__index = ReqlessJob

local ReqlessThrottle = {
  ns = Reqless.ns .. 'th:'
}
ReqlessThrottle.__index = ReqlessThrottle

local ReqlessRecurringJob = {}
ReqlessRecurringJob.__index = ReqlessRecurringJob

Reqless.config = {}

local function table_extend(self, other)
  for _, v in ipairs(other) do
    table.insert(self, v)
  end
end

function Reqless.publish(channel, message)
  redis.call('publish', Reqless.ns .. channel, message)
end

function Reqless.job(jid)
  assert(jid, 'Job(): no jid provided')
  local job = {}
  setmetatable(job, ReqlessJob)
  job.jid = jid
  return job
end

function Reqless.recurring(jid)
  assert(jid, 'Recurring(): no jid provided')
  local job = {}
  setmetatable(job, ReqlessRecurringJob)
  job.jid = jid
  return job
end

function Reqless.throttle(tid)
  assert(tid, 'Throttle(): no tid provided')
  local throttle = ReqlessThrottle.data({id = tid})
  setmetatable(throttle, ReqlessThrottle)

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

function Reqless.failed(group, start, limit)
  start = assert(tonumber(start or 0),
    'Failed(): Arg "start" is not a number: ' .. (start or 'nil'))
  limit = assert(tonumber(limit or 25),
    'Failed(): Arg "limit" is not a number: ' .. (limit or 'nil'))

  if group then
    return {
      total = redis.call('llen', 'rql:f:' .. group),
      jobs  = redis.call('lrange', 'rql:f:' .. group, start, start + limit - 1)
    }
  end

  local response = {}
  local groups = redis.call('smembers', 'rql:failures')
  for _, group in ipairs(groups) do
    response[group] = redis.call('llen', 'rql:f:' .. group)
  end
  return response
end

function Reqless.jobs(now, state, ...)
  assert(state, 'Jobs(): Arg "state" missing')
  if state == 'complete' then
    local offset = assert(tonumber(arg[1] or 0),
      'Jobs(): Arg "offset" not a number: ' .. tostring(arg[1]))
    local count  = assert(tonumber(arg[2] or 25),
      'Jobs(): Arg "count" not a number: ' .. tostring(arg[2]))
    return redis.call('zrevrange', 'rql:completed', offset,
      offset + count - 1)
  end

  local name  = assert(arg[1], 'Jobs(): Arg "queue" missing')
  local offset = assert(tonumber(arg[2] or 0),
    'Jobs(): Arg "offset" not a number: ' .. tostring(arg[2]))
  local count  = assert(tonumber(arg[3] or 25),
    'Jobs(): Arg "count" not a number: ' .. tostring(arg[3]))

  local queue = Reqless.queue(name)
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

function Reqless.track(now, command, jid)
  if command ~= nil then
    assert(jid, 'Track(): Arg "jid" missing')
    assert(Reqless.job(jid):exists(), 'Track(): Job does not exist')
    if string.lower(command) == 'track' then
      Reqless.publish('track', jid)
      return redis.call('zadd', 'rql:tracked', now, jid)
    elseif string.lower(command) == 'untrack' then
      Reqless.publish('untrack', jid)
      return redis.call('zrem', 'rql:tracked', jid)
    end
    error('Track(): Unknown action "' .. command .. '"')
  end

  local response = {
    jobs = {},
    expired = {},
  }
  local jids = redis.call('zrange', 'rql:tracked', 0, -1)
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

function Reqless.tag(now, command, ...)
  assert(command,
    'Tag(): Arg "command" must be "add", "remove", "get" or "top"')

  if command == 'add' then
    local jid  = assert(arg[1], 'Tag(): Arg "jid" missing')
    local tags = redis.call('hget', ReqlessJob.ns .. jid, 'tags')
    if tags then
      tags = cjson.decode(tags)
      local _tags = {}
      for _, v in ipairs(tags) do _tags[v] = true end

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
    if tags then
      tags = cjson.decode(tags)
      local _tags = {}
      for _, v in ipairs(tags) do _tags[v] = true end

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
      total = redis.call('zcard', 'rql:t:' .. tag),
      jobs  = redis.call('zrange', 'rql:t:' .. tag, offset, offset + count - 1)
    }
  elseif command == 'top' then
    local offset = assert(tonumber(arg[1] or 0) , 'Tag(): Arg "offset" not a number: ' .. tostring(arg[1]))
    local count  = assert(tonumber(arg[2] or 25), 'Tag(): Arg "count" not a number: ' .. tostring(arg[2]))
    return redis.call('zrevrangebyscore', 'rql:tags', '+inf', 2, 'limit', offset, count)
  end

  error('Tag(): First argument must be "add", "remove" or "get"')
end

function Reqless.cancel(now, ...)
  local dependents = {}
  for _, jid in ipairs(arg) do
    dependents[jid] = redis.call(
      'smembers', ReqlessJob.ns .. jid .. '-dependents') or {}
  end

  for _, jid in ipairs(arg) do
    for j, dep in ipairs(dependents[jid]) do
      if dependents[dep] == nil then
        error('Cancel(): ' .. jid .. ' is a dependency of ' .. dep ..
           ' but is not mentioned to be canceled')
      end
    end
  end

  for _, jid in ipairs(arg) do
    local state, queue, failure, worker = unpack(redis.call(
      'hmget', ReqlessJob.ns .. jid, 'state', 'queue', 'failure', 'worker'))

    if state ~= 'complete' then
      local encoded = cjson.encode({
        jid    = jid,
        worker = worker,
        event  = 'canceled',
        queue  = queue
      })
      Reqless.publish('log', encoded)

      if worker and (worker ~= '') then
        redis.call('zrem', 'rql:w:' .. worker .. ':jobs', jid)
        Reqless.publish('w:' .. worker, encoded)
      end

      if queue then
        local queue = Reqless.queue(queue)
        queue:remove_job(jid)
      end

      local job = Reqless.job(jid)

      job:throttles_release(now)

      for _, j in ipairs(redis.call(
        'smembers', ReqlessJob.ns .. jid .. '-dependencies')) do
        redis.call('srem', ReqlessJob.ns .. j .. '-dependents', jid)
      end

      if state == 'failed' then
        failure = cjson.decode(failure)
        redis.call('lrem', 'rql:f:' .. failure.group, 0, jid)
        if redis.call('llen', 'rql:f:' .. failure.group) == 0 then
          redis.call('srem', 'rql:failures', failure.group)
        end
        local bin = failure.when - (failure.when % 86400)
        local failed = redis.call(
          'hget', 'rql:s:stats:' .. bin .. ':' .. queue, 'failed')
        redis.call('hset',
          'rql:s:stats:' .. bin .. ':' .. queue, 'failed', failed - 1)
      end

      job:delete()

      if redis.call('zscore', 'rql:tracked', jid) ~= false then
        Reqless.publish('canceled', jid)
      end
    end
  end

  return arg
end

Reqless.config.defaults = {
  ['application']        = 'reqless',
  ['heartbeat']          = 60,
  ['grace-period']       = 10,
  ['stats-history']      = 30,
  ['histogram-history']  = 7,
  ['jobs-history-count'] = 50000,
  ['jobs-history']       = 604800
}

Reqless.config.get = function(key, default)
  if key then
    return redis.call('hget', 'rql:config', key) or
      Reqless.config.defaults[key] or default
  end

  local reply = redis.call('hgetall', 'rql:config')
  for i = 1, #reply, 2 do
    Reqless.config.defaults[reply[i]] = reply[i + 1]
  end
  return Reqless.config.defaults
end

Reqless.config.set = function(option, value)
  assert(option, 'config.set(): Arg "option" missing')
  assert(value , 'config.set(): Arg "value" missing')
  Reqless.publish('log', cjson.encode({
    event  = 'config_set',
    option = option,
    value  = value
  }))

  redis.call('hset', 'rql:config', option, value)
end

Reqless.config.unset = function(option)
  assert(option, 'config.unset(): Arg "option" missing')
  Reqless.publish('log', cjson.encode({
    event  = 'config_unset',
    option = option
  }))

  redis.call('hdel', 'rql:config', option)
end

function ReqlessJob:data(...)
  local job = redis.call(
      'hmget', ReqlessJob.ns .. self.jid, 'jid', 'klass', 'state', 'queue',
      'worker', 'priority', 'expires', 'retries', 'remaining', 'data',
      'tags', 'failure', 'throttles', 'spawned_from_jid')

  if not job[1] then
    return nil
  end

  local data = {
    jid = job[1],
    klass = job[2],
    state = job[3],
    queue = job[4],
    worker = job[5] or '',
    tracked = redis.call('zscore', 'rql:tracked', self.jid) ~= false,
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
    local response = {}
    for _, key in ipairs(arg) do
      table.insert(response, data[key])
    end
    return response
  end

  return data
end

function ReqlessJob:complete(now, worker, queue_name, raw_data, ...)
  assert(worker, 'Complete(): Arg "worker" missing')
  assert(queue_name , 'Complete(): Arg "queue_name" missing')
  local data = assert(cjson.decode(raw_data),
    'Complete(): Arg "data" missing or not JSON: ' .. tostring(raw_data))

  local options = {}
  for i = 1, #arg, 2 do options[arg[i]] = arg[i + 1] end

  local next_queue_name = options['next']
  local delay = assert(tonumber(options['delay'] or 0))
  local depends = assert(cjson.decode(options['depends'] or '[]'),
    'Complete(): Arg "depends" not JSON: ' .. tostring(options['depends']))

  if options['delay'] and next_queue_name == nil then
    error('Complete(): "delay" cannot be used without a "next".')
  end

  if options['depends'] and next_queue_name == nil then
    error('Complete(): "depends" cannot be used without a "next".')
  end

  local bin = now - (now % 86400)

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

  self:history(now, 'done')

  if raw_data then
    redis.call('hset', ReqlessJob.ns .. self.jid, 'data', raw_data)
  end

  local queue = Reqless.queue(queue_name)
  queue:remove_job(self.jid)

  self:throttles_release(now)

  local time = tonumber(
    redis.call('hget', ReqlessJob.ns .. self.jid, 'time') or now)
  local waiting = now - time
  queue:stat(now, 'run', waiting)
  redis.call('hset', ReqlessJob.ns .. self.jid,
    'time', string.format("%.20f", now))

  redis.call('zrem', 'rql:w:' .. worker .. ':jobs', self.jid)

  if redis.call('zscore', 'rql:tracked', self.jid) ~= false then
    Reqless.publish('completed', self.jid)
  end

  if next_queue_name then
    local next_queue = Reqless.queue(next_queue_name)
    Reqless.publish('log', cjson.encode({
      jid = self.jid,
      event = 'advanced',
      queue = queue_name,
      to = next_queue_name,
    }))

    self:history(now, 'put', {queue = next_queue_name})

    if redis.call('zscore', 'rql:queues', next_queue_name) == false then
      redis.call('zadd', 'rql:queues', now, next_queue_name)
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

    local count = 0
    for _, j in ipairs(depends) do
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
        next_queue.depends.add(now, self.jid)
        redis.call('hset', ReqlessJob.ns .. self.jid, 'scheduled', now + delay)
      end
      return 'depends'
    end

    next_queue.work.add(now, priority, self.jid)
    return 'waiting'
  end
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

  local count = Reqless.config.get('jobs-history-count')
  local time  = Reqless.config.get('jobs-history')

  count = tonumber(count or 50000)
  time  = tonumber(time  or 7 * 24 * 60 * 60)

  redis.call('zadd', 'rql:completed', now, self.jid)

  local jids = redis.call('zrangebyscore', 'rql:completed', 0, now - time)
  for _, jid in ipairs(jids) do
    Reqless.job(jid):delete()
  end

  redis.call('zremrangebyscore', 'rql:completed', 0, now - time)

  jids = redis.call('zrange', 'rql:completed', 0, (-1-count))
  for _, jid in ipairs(jids) do
    Reqless.job(jid):delete()
  end
  redis.call('zremrangebyrank', 'rql:completed', 0, (-1-count))

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

  redis.call('del', ReqlessJob.ns .. self.jid .. '-dependents')

  return 'complete'
end

function ReqlessJob:fail(now, worker, group, message, data)
  local worker  = assert(worker           , 'Fail(): Arg "worker" missing')
  local group   = assert(group            , 'Fail(): Arg "group" missing')
  local message = assert(message          , 'Fail(): Arg "message" missing')

  local bin = now - (now % 86400)

  if data then
    data = cjson.decode(data)
  end

  local queue_name, state, oldworker = unpack(redis.call(
    'hmget', ReqlessJob.ns .. self.jid, 'queue', 'state', 'worker'))

  if not state then
    error('Fail(): Job does not exist')
  elseif state ~= 'running' then
    error('Fail(): Job not currently running: ' .. state)
  elseif worker ~= oldworker then
    error('Fail(): Job running with another worker: ' .. oldworker)
  end

  Reqless.publish('log', cjson.encode({
    jid = self.jid,
    event = 'failed',
    worker = worker,
    group = group,
    message = message,
  }))

  if redis.call('zscore', 'rql:tracked', self.jid) ~= false then
    Reqless.publish('failed', self.jid)
  end

  redis.call('zrem', 'rql:w:' .. worker .. ':jobs', self.jid)

  self:history(now, 'failed', {worker = worker, group = group})

  redis.call('hincrby', 'rql:s:stats:' .. bin .. ':' .. queue_name, 'failures', 1)
  redis.call('hincrby', 'rql:s:stats:' .. bin .. ':' .. queue_name, 'failed'  , 1)

  local queue = Reqless.queue(queue_name)
  queue:remove_job(self.jid)

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

  redis.call('sadd', 'rql:failures', group)
  redis.call('lpush', 'rql:f:' .. group, self.jid)


  return self.jid
end

function ReqlessJob:retry(now, queue_name, worker, delay, group, message)
  assert(queue_name , 'Retry(): Arg "queue_name" missing')
  assert(worker, 'Retry(): Arg "worker" missing')
  delay = assert(tonumber(delay or 0),
    'Retry(): Arg "delay" not a number: ' .. tostring(delay))

  local old_queue_name, state, retries, oldworker, priority, failure = unpack(
    redis.call('hmget', ReqlessJob.ns .. self.jid, 'queue', 'state',
      'retries', 'worker', 'priority', 'failure'))

  if oldworker == false then
    error('Retry(): Job does not exist')
  elseif state ~= 'running' then
    error('Retry(): Job is not currently running: ' .. state)
  elseif oldworker ~= worker then
    error('Retry(): Job has been given to another worker: ' .. oldworker)
  end

  local remaining = tonumber(redis.call(
    'hincrby', ReqlessJob.ns .. self.jid, 'remaining', -1))
  redis.call('hdel', ReqlessJob.ns .. self.jid, 'grace')

  Reqless.queue(old_queue_name).locks.remove(self.jid)

  self:throttles_release(now)

  redis.call('zrem', 'rql:w:' .. worker .. ':jobs', self.jid)

  if remaining < 0 then
    local group = group or 'failed-retries-' .. queue_name
    self:history(now, 'failed-retries', {group = group})

    redis.call('hmset', ReqlessJob.ns .. self.jid, 'state', 'failed',
      'worker', '',
      'expires', '')
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

    redis.call('sadd', 'rql:failures', group)
    redis.call('lpush', 'rql:f:' .. group, self.jid)
    local bin = now - (now % 86400)
    redis.call('hincrby', 'rql:s:stats:' .. bin .. ':' .. queue_name, 'failures', 1)
    redis.call('hincrby', 'rql:s:stats:' .. bin .. ':' .. queue_name, 'failed'  , 1)
  else
    local queue = Reqless.queue(queue_name)
    if delay > 0 then
      queue.scheduled.add(now + delay, self.jid)
      redis.call('hset', ReqlessJob.ns .. self.jid, 'state', 'scheduled')
    else
      queue.work.add(now, priority, self.jid)
      redis.call('hset', ReqlessJob.ns .. self.jid, 'state', 'waiting')
    end

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

function ReqlessJob:depends(now, command, ...)
  assert(command, 'Depends(): Arg "command" missing')
  local state = redis.call('hget', ReqlessJob.ns .. self.jid, 'state')
  if state ~= 'depends' then
    error('Depends(): Job ' .. self.jid ..
      ' not in the depends state: ' .. tostring(state))
  end

  if command == 'on' then
    for _, j in ipairs(arg) do
      local state = redis.call('hget', ReqlessJob.ns .. j, 'state')
      if (state and state ~= 'complete') then
        redis.call(
          'sadd', ReqlessJob.ns .. j .. '-dependents'  , self.jid)
        redis.call(
          'sadd', ReqlessJob.ns .. self.jid .. '-dependencies', j)
      end
    end
    return true
  elseif command == 'off' then
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

  error('Depends(): Argument "command" must be "on" or "off"')
end

function ReqlessJob:heartbeat(now, worker, data)
  assert(worker, 'Heatbeat(): Arg "worker" missing')

  local queue_name = redis.call('hget', ReqlessJob.ns .. self.jid, 'queue') or ''
  local expires = now + tonumber(
    Reqless.config.get(queue_name .. '-heartbeat') or
    Reqless.config.get('heartbeat', 60))

  if data then
    data = cjson.decode(data)
  end

  local job_worker, state = unpack(
    redis.call('hmget', ReqlessJob.ns .. self.jid, 'worker', 'state'))
  if job_worker == false then
    error('Heartbeat(): Job does not exist')
  elseif state ~= 'running' then
    error('Heartbeat(): Job not currently running: ' .. state)
  elseif job_worker ~= worker or #job_worker == 0 then
    error('Heartbeat(): Job given out to another worker: ' .. job_worker)
  end

  if data then
    redis.call('hmset', ReqlessJob.ns .. self.jid, 'expires',
      expires, 'worker', worker, 'data', cjson.encode(data))
  else
    redis.call('hmset', ReqlessJob.ns .. self.jid,
      'expires', expires, 'worker', worker)
  end

  redis.call('zadd', 'rql:w:' .. worker .. ':jobs', expires, self.jid)

  local queue = Reqless.queue(
    redis.call('hget', ReqlessJob.ns .. self.jid, 'queue'))
  queue.locks.add(expires, self.jid)
  return expires
end

function ReqlessJob:priority(priority)
  priority = assert(tonumber(priority),
    'Priority(): Arg "priority" missing or not a number: ' ..
    tostring(priority))

  local queue_name = redis.call('hget', ReqlessJob.ns .. self.jid, 'queue')

  if queue_name == nil then
    error('Priority(): Job ' .. self.jid .. ' does not exist')
  elseif queue_name == '' then
    redis.call('hset', ReqlessJob.ns .. self.jid, 'priority', priority)
    return priority
  end

  local queue = Reqless.queue(queue_name)
  if queue.work.score(self.jid) then
    queue.work.add(0, priority, self.jid)
  end
  redis.call('hset', ReqlessJob.ns .. self.jid, 'priority', priority)
  return priority
end

function ReqlessJob:update(data)
  local tmp = {}
  for k, v in pairs(data) do
    table.insert(tmp, k)
    table.insert(tmp, v)
  end
  redis.call('hmset', ReqlessJob.ns .. self.jid, unpack(tmp))
end

function ReqlessJob:timeout(now)
  local queue_name, state, worker = unpack(redis.call('hmget',
    ReqlessJob.ns .. self.jid, 'queue', 'state', 'worker'))
  if queue_name == nil then
    error('Timeout(): Job does not exist')
  elseif state ~= 'running' then
    error('Timeout(): Job ' .. self.jid .. ' not running')
  end
  self:history(now, 'timed-out')
  local queue = Reqless.queue(queue_name)
  queue.locks.remove(self.jid)

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

function ReqlessJob:exists()
  return redis.call('exists', ReqlessJob.ns .. self.jid) == 1
end

function ReqlessJob:history(now, what, item)
  local history = redis.call('hget', ReqlessJob.ns .. self.jid, 'history')
  if history then
    history = cjson.decode(history)
    for _, value in ipairs(history) do
      redis.call('rpush', ReqlessJob.ns .. self.jid .. '-history',
        cjson.encode({math.floor(value.put), 'put', {queue = value.queue}}))

      if value.popped then
        redis.call('rpush', ReqlessJob.ns .. self.jid .. '-history',
          cjson.encode({math.floor(value.popped), 'popped',
            {worker = value.worker}}))
      end

      if value.failed then
        redis.call('rpush', ReqlessJob.ns .. self.jid .. '-history',
          cjson.encode(
            {math.floor(value.failed), 'failed', nil}))
      end

      if value.done then
        redis.call('rpush', ReqlessJob.ns .. self.jid .. '-history',
          cjson.encode(
            {math.floor(value.done), 'done', nil}))
      end
    end
    redis.call('hdel', ReqlessJob.ns .. self.jid, 'history')
  end

  if what == nil then
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

  local count = tonumber(Reqless.config.get('max-job-history', 100))
  if count > 0 then
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
  if not self._throttles then
    self._throttles = cjson.decode(redis.call('hget', ReqlessJob.ns .. self.jid, 'throttles') or '[]')
  end

  return self._throttles
end

function ReqlessJob:delete()
  local tags = redis.call('hget', ReqlessJob.ns .. self.jid, 'tags') or '[]'
  tags = cjson.decode(tags)
  for _, tag in ipairs(tags) do
    self:remove_tag(tag)
  end
  redis.call('del', ReqlessJob.ns .. self.jid)
  redis.call('del', ReqlessJob.ns .. self.jid .. '-history')
  redis.call('del', ReqlessJob.ns .. self.jid .. '-dependencies')
end

function ReqlessJob:insert_tag(now, tag)
  redis.call('zadd', 'rql:t:' .. tag, now, self.jid)
  redis.call('zincrby', 'rql:tags', 1, tag)
end

function ReqlessJob:remove_tag(tag)
  local namespaced_tag = 'rql:t:' .. tag

  redis.call('zrem', namespaced_tag, self.jid)

  local remaining = redis.call('zcard', namespaced_tag)

  if tonumber(remaining) == 0 then
    redis.call('zrem', 'rql:tags', tag)
  else
    redis.call('zincrby', 'rql:tags', -1, tag)
  end
end
function Reqless.queue(name)
  assert(name, 'Queue(): no queue name provided')
  local queue = {}
  setmetatable(queue, ReqlessQueue)
  queue.name = name

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
      if now then
        return redis.call('zcount', queue:prefix('locks'), 0, now)
      else
        return redis.call('zcard', queue:prefix('locks'))
      end
    end
  }

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

function ReqlessQueue:prefix(group)
  if group then
    return ReqlessQueue.ns .. self.name .. '-' .. group
  end

  return ReqlessQueue.ns .. self.name
end

function ReqlessQueue:stats(now, date)
  date = assert(tonumber(date),
    'Stats(): Arg "date" missing or not a number: ' .. (date or 'nil'))

  local bin = date - (date % 86400)

  local histokeys = {
    's0','s1','s2','s3','s4','s5','s6','s7','s8','s9','s10','s11','s12','s13','s14','s15','s16','s17','s18','s19','s20','s21','s22','s23','s24','s25','s26','s27','s28','s29','s30','s31','s32','s33','s34','s35','s36','s37','s38','s39','s40','s41','s42','s43','s44','s45','s46','s47','s48','s49','s50','s51','s52','s53','s54','s55','s56','s57','s58','s59',
    'm1','m2','m3','m4','m5','m6','m7','m8','m9','m10','m11','m12','m13','m14','m15','m16','m17','m18','m19','m20','m21','m22','m23','m24','m25','m26','m27','m28','m29','m30','m31','m32','m33','m34','m35','m36','m37','m38','m39','m40','m41','m42','m43','m44','m45','m46','m47','m48','m49','m50','m51','m52','m53','m54','m55','m56','m57','m58','m59',
    'h1','h2','h3','h4','h5','h6','h7','h8','h9','h10','h11','h12','h13','h14','h15','h16','h17','h18','h19','h20','h21','h22','h23',
    'd1','d2','d3','d4','d5','d6'
  }

  local mkstats = function(name, bin, queue)
    local results = {}

    local key = 'rql:s:' .. name .. ':' .. bin .. ':' .. queue
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

  local retries, failed, failures = unpack(redis.call('hmget', 'rql:s:stats:' .. bin .. ':' .. self.name, 'retries', 'failed', 'failures'))
  return {
    retries  = tonumber(retries  or 0),
    failed   = tonumber(failed   or 0),
    failures = tonumber(failures or 0),
    wait     = mkstats('wait', bin, self.name),
    run      = mkstats('run' , bin, self.name)
  }
end

function ReqlessQueue:peek(now, offset, count)
  offset = assert(tonumber(offset),
    'Peek(): Arg "offset" missing or not a number: ' .. tostring(offset))

  count = assert(tonumber(count),
    'Peek(): Arg "count" missing or not a number: ' .. tostring(count))

  if count <= 0 then
    return {}
  end

  local count_with_offset = offset + count

  local jids = self.locks.expired(now, 0, count_with_offset)

  local remaining_capacity = count_with_offset - #jids

  self:check_recurring(now, remaining_capacity)

  self:check_scheduled(now, remaining_capacity)

  if offset > #jids then
    return self.work.peek(offset - #jids, count)
  end

  table_extend(jids, self.work.peek(0, remaining_capacity))

  if #jids < offset then
    return {}
  end

  return {unpack(jids, offset + 1, count_with_offset)}
end

function ReqlessQueue:paused()
  return redis.call('sismember', 'rql:paused_queues', self.name) == 1
end

function ReqlessQueue.pause(now, ...)
  redis.call('sadd', 'rql:paused_queues', unpack(arg))
end

function ReqlessQueue.unpause(...)
  redis.call('srem', 'rql:paused_queues', unpack(arg))
end

function ReqlessQueue:pop(now, worker, count)
  assert(worker, 'Pop(): Arg "worker" missing')
  count = assert(tonumber(count),
    'Pop(): Arg "count" missing or not a number: ' .. tostring(count))

  if self:paused() then
    return {}
  end

  redis.call('zadd', 'rql:workers', now, worker)

  local dead_jids = self:invalidate_locks(now, count) or {}
  local popped = {}

  for _, jid in ipairs(dead_jids) do
    local success = self:pop_job(now, worker, Reqless.job(jid))
    if success then
      table.insert(popped, jid)
    end
  end

  if not Reqless.throttle(ReqlessQueue.ns .. self.name):available() then
    return popped
  end


  self:check_recurring(now, count - #dead_jids)

  self:check_scheduled(now, count - #dead_jids)


  local pop_retry_limit = tonumber(
    Reqless.config.get(self.name .. '-max-pop-retry') or
    Reqless.config.get('max-pop-retry', 1)
  )

  while #popped < count and pop_retry_limit > 0 do

    local jids = self.work.peek(0, count - #popped) or {}

    if #jids == 0 then
      break
    end


    for _, jid in ipairs(jids) do
      local job = Reqless.job(jid)
      if job:throttles_acquire(now) then
        local success = self:pop_job(now, worker, job)
        if success then
          table.insert(popped, jid)
        end
      else
        self:throttle(now, job)
      end
    end

    self.work.remove(unpack(jids))

    pop_retry_limit = pop_retry_limit - 1
  end

  return popped
end

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
  if not job_state then
    return false
  end

  state = unpack(job_state)
  job:history(now, 'popped', {worker = worker})

  local expires = now + tonumber(
    Reqless.config.get(self.name .. '-heartbeat') or
    Reqless.config.get('heartbeat', 60))

  local time = tonumber(redis.call('hget', ReqlessJob.ns .. jid, 'time') or now)
  local waiting = now - time
  self:stat(now, 'wait', waiting)
  redis.call('hset', ReqlessJob.ns .. jid,
    'time', string.format("%.20f", now))

  redis.call('zadd', 'rql:w:' .. worker .. ':jobs', expires, jid)

  job:update({
    worker  = worker,
    expires = expires,
    state   = 'running'
  })

  self.locks.add(expires, jid)

  local tracked = redis.call('zscore', 'rql:tracked', jid) ~= false
  if tracked then
    Reqless.publish('popped', jid)
  end
  return true
end

function ReqlessQueue:stat(now, stat, val)
  local bin = now - (now % 86400)
  local key = 'rql:s:' .. stat .. ':' .. bin .. ':' .. self.name

  local count, mean, vk = unpack(
    redis.call('hmget', key, 'total', 'mean', 'vk'))

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

function ReqlessQueue:put(now, worker, jid, klass, raw_data, delay, ...)
  assert(jid  , 'Put(): Arg "jid" missing')
  assert(klass, 'Put(): Arg "klass" missing')
  local data = assert(cjson.decode(raw_data),
    'Put(): Arg "data" missing or not JSON: ' .. tostring(raw_data))
  delay = assert(tonumber(delay),
    'Put(): Arg "delay" not a number: ' .. tostring(delay))

  if #arg % 2 == 1 then
    error('Odd number of additional args: ' .. tostring(arg))
  end
  local options = {}
  for i = 1, #arg, 2 do options[arg[i]] = arg[i + 1] end

  local job = Reqless.job(jid)
  local priority, tags, oldqueue, state, failure, retries, oldworker =
    unpack(redis.call('hmget', ReqlessJob.ns .. jid, 'priority', 'tags',
      'queue', 'state', 'failure', 'retries', 'worker'))

  if tags then
    Reqless.tag(now, 'remove', jid, unpack(cjson.decode(tags)))
  end

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

  if #depends > 0 then
    local new = {}
    for _, d in ipairs(depends) do new[d] = 1 end

    local original = redis.call(
      'smembers', ReqlessJob.ns .. jid .. '-dependencies')
    for _, dep in pairs(original) do
      if new[dep] == nil then
        redis.call('srem', ReqlessJob.ns .. dep .. '-dependents'  , jid)
        redis.call('srem', ReqlessJob.ns .. jid .. '-dependencies', dep)
      end
    end
  end

  Reqless.publish('log', cjson.encode({
    jid   = jid,
    event = 'put',
    queue = self.name
  }))

  job:history(now, 'put', {queue = self.name})

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

  if oldworker and oldworker ~= '' then
    redis.call('zrem', 'rql:w:' .. oldworker .. ':jobs', jid)
    if oldworker ~= worker then
      local encoded = cjson.encode({
        jid    = jid,
        event  = 'lock_lost',
        worker = oldworker
      })
      Reqless.publish('w:' .. oldworker, encoded)
      Reqless.publish('log', encoded)
    end
  end

  if state == 'complete' then
    redis.call('zrem', 'rql:completed', jid)
  end

  for _, tag in ipairs(tags) do
    Reqless.job(jid):insert_tag(now, tag)
  end

  if state == 'failed' then
    failure = cjson.decode(failure)
    redis.call('lrem', 'rql:f:' .. failure.group, 0, jid)
    if redis.call('llen', 'rql:f:' .. failure.group) == 0 then
      redis.call('srem', 'rql:failures', failure.group)
    end
    local bin = failure.when - (failure.when % 86400)
    redis.call('hincrby', 'rql:s:stats:' .. bin .. ':' .. self.name, 'failed'  , -1)
  end

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

  redis.call('hmset', ReqlessJob.ns .. jid, unpack(data))

  for _, j in ipairs(depends) do
    local state = redis.call('hget', ReqlessJob.ns .. j, 'state')
    if (state and state ~= 'complete') then
      redis.call('sadd', ReqlessJob.ns .. j .. '-dependents'  , jid)
      redis.call('sadd', ReqlessJob.ns .. jid .. '-dependencies', j)
    end
  end

  if delay > 0 then
    if redis.call('scard', ReqlessJob.ns .. jid .. '-dependencies') > 0 then
      self.depends.add(now, jid)
      redis.call('hmset', ReqlessJob.ns .. jid,
        'state', 'depends',
        'scheduled', now + delay)
    else
      self.scheduled.add(now + delay, jid)
    end
  else
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

  if redis.call('zscore', 'rql:queues', self.name) == false then
    redis.call('zadd', 'rql:queues', now, self.name)
  end

  if redis.call('zscore', 'rql:tracked', jid) ~= false then
    Reqless.publish('put', jid)
  end

  return jid
end

function ReqlessQueue:unfail(now, group, count)
  assert(group, 'Unfail(): Arg "group" missing')
  count = assert(tonumber(count or 25),
    'Unfail(): Arg "count" not a number: ' .. tostring(count))

  local jids = redis.call('lrange', 'rql:f:' .. group, -count, -1)

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

  redis.call('ltrim', 'rql:f:' .. group, 0, -count - 1)
  if (redis.call('llen', 'rql:f:' .. group) == 0) then
    redis.call('srem', 'rql:failures', group)
  end

  return #jids
end

function ReqlessQueue:recur(now, jid, klass, raw_data, spec, ...)
  assert(jid  , 'RecurringJob On(): Arg "jid" missing')
  assert(klass, 'RecurringJob On(): Arg "klass" missing')
  assert(spec , 'RecurringJob On(): Arg "spec" missing')
  local data = assert(cjson.decode(raw_data),
    'RecurringJob On(): Arg "data" not JSON: ' .. tostring(raw_data))

  if spec == 'interval' then
    local interval = assert(tonumber(arg[1]),
      'Recur(): Arg "interval" not a number: ' .. tostring(arg[1]))
    local offset   = assert(tonumber(arg[2]),
      'Recur(): Arg "offset" not a number: '   .. tostring(arg[2]))
    if interval <= 0 then
      error('Recur(): Arg "interval" must be greater than 0')
    end

    if #arg % 2 == 1 then
      error('Odd number of additional args: ' .. tostring(arg))
    end

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

    local count, old_queue = unpack(redis.call('hmget', 'rql:r:' .. jid, 'count', 'queue'))
    count = count or 0

    local throttles = options['throttles'] or {}

    if old_queue then
      Reqless.queue(old_queue).recurring.remove(jid)

      for index, throttle_name in ipairs(throttles) do
        if throttle_name == old_queue then
          table.remove(throttles, index)
        end
      end
    end

    table.insert(throttles, ReqlessQueue.ns .. self.name)

    redis.call('hmset', 'rql:r:' .. jid,
      'jid'      , jid,
      'klass'    , klass,
      'data'     , raw_data,
      'priority' , options.priority,
      'tags'     , cjson.encode(options.tags or {}),
      'state'    , 'recur',
      'queue'    , self.name,
      'type'     , 'interval',
      'count'    , count,
      'interval' , interval,
      'retries'  , options.retries,
      'backlog'  , options.backlog,
      'throttles', cjson.encode(throttles))
    self.recurring.add(now + offset, jid)

    if redis.call('zscore', 'rql:queues', self.name) == false then
      redis.call('zadd', 'rql:queues', now, self.name)
    end

    return jid
  end

  error('Recur(): schedule type "' .. tostring(spec) .. '" unknown')
end

function ReqlessQueue:length()
  return  self.locks.length() + self.work.length() + self.scheduled.length()
end

function ReqlessQueue:remove_job(jid)
  self.work.remove(jid)
  self.locks.remove(jid)
  self.throttled.remove(jid)
  self.depends.remove(jid)
  self.scheduled.remove(jid)
end

function ReqlessQueue:check_recurring(now, count)
  if count <= 0 then
    return
  end
  local moved = 0
  local r = self.recurring.peek(now, 0, count)
  for _, jid in ipairs(r) do
    local r = redis.call('hmget', 'rql:r:' .. jid, 'klass', 'data', 'priority',
        'tags', 'retries', 'interval', 'backlog', 'throttles')
    local klass, data, priority, tags, retries, interval, backlog, throttles = unpack(
      redis.call('hmget', 'rql:r:' .. jid, 'klass', 'data', 'priority',
        'tags', 'retries', 'interval', 'backlog', 'throttles'))
    local _tags = cjson.decode(tags)
    local score = math.floor(tonumber(self.recurring.score(jid)))
    interval = tonumber(interval)

    backlog = tonumber(backlog or 0)
    if backlog ~= 0 then
      local num = ((now - score) / interval)
      if num > backlog then
        score = score + (
          math.ceil(num - backlog) * interval
        )
      end
    end

    while (score <= now) and (moved < count) do
      local count = redis.call('hincrby', 'rql:r:' .. jid, 'count', 1)
      moved = moved + 1

      local child_jid = jid .. '-' .. count

      for _, tag in ipairs(_tags) do
        Reqless.job(child_jid):insert_tag(now, tag)
      end

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

      self.work.add(score, priority, child_jid)

      score = score + interval
      self.recurring.add(score, jid)
    end
  end
end

function ReqlessQueue:check_scheduled(now, count)
  if count <= 0 then
    return
  end
  local scheduled = self.scheduled.ready(now, 0, count)
  for _, jid in ipairs(scheduled) do
    local priority = tonumber(
      redis.call('hget', ReqlessJob.ns .. jid, 'priority') or 0)
    self.work.add(now, priority, jid)
    self.scheduled.remove(jid)

    redis.call('hset', ReqlessJob.ns .. jid, 'state', 'waiting')
  end
end

function ReqlessQueue:invalidate_locks(now, count)
  local jids = {}
  for _, jid in ipairs(self.locks.expired(now, 0, count)) do
    local worker, failure = unpack(
      redis.call('hmget', ReqlessJob.ns .. jid, 'worker', 'failure'))
    redis.call('zrem', 'rql:w:' .. worker .. ':jobs', jid)

    local grace_period = tonumber(Reqless.config.get('grace-period'))

    local courtesy_sent = tonumber(
      redis.call('hget', ReqlessJob.ns .. jid, 'grace') or 0)

    local send_message = (courtesy_sent ~= 1)
    local invalidate   = not send_message

    if grace_period <= 0 then
      send_message = true
      invalidate   = true
    end

    if send_message then
      if redis.call('zscore', 'rql:tracked', jid) ~= false then
        Reqless.publish('stalled', jid)
      end
      Reqless.job(jid):history(now, 'timed-out')
      redis.call('hset', ReqlessJob.ns .. jid, 'grace', 1)

      local encoded = cjson.encode({
        jid    = jid,
        event  = 'lock_lost',
        worker = worker,
      })
      Reqless.publish('w:' .. worker, encoded)
      Reqless.publish('log', encoded)
      self.locks.add(now + grace_period, jid)

      local bin = now - (now % 86400)
      redis.call('hincrby',
        'rql:s:stats:' .. bin .. ':' .. self.name, 'retries', 1)
    end

    if invalidate then
      redis.call('hdel', ReqlessJob.ns .. jid, 'grace', 0)

      local remaining = tonumber(redis.call(
        'hincrby', ReqlessJob.ns .. jid, 'remaining', -1))

      if remaining < 0 then
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
        redis.call('hset', ReqlessJob.ns .. jid,
        'failure', cjson.encode({
          group   = group,
          message = 'Job exhausted retries in queue "' .. self.name .. '"',
          when    = now,
          worker  = unpack(job:data('worker'))
        }))

        redis.call('sadd', 'rql:failures', group)
        redis.call('lpush', 'rql:f:' .. group, jid)

        if redis.call('zscore', 'rql:tracked', jid) ~= false then
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

        local bin = now - (now % 86400)
        redis.call('hincrby',
          'rql:s:stats:' .. bin .. ':' .. self.name, 'failures', 1)
        redis.call('hincrby',
          'rql:s:stats:' .. bin .. ':' .. self.name, 'failed'  , 1)
      else
        table.insert(jids, jid)
      end
    end
  end

  return jids
end

function ReqlessQueue.deregister(...)
  redis.call('zrem', Reqless.ns .. 'queues', unpack(arg))
end

function ReqlessQueue.counts(now, name)
  if name then
    local queue = Reqless.queue(name)
    local stalled = queue.locks.length(now)
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

  local queues = redis.call('zrange', 'rql:queues', 0, -1)
  local response = {}
  for _, qname in ipairs(queues) do
    table.insert(response, ReqlessQueue.counts(now, qname))
  end
  return response
end
function ReqlessRecurringJob:data()
  local job = redis.call(
    'hmget', 'rql:r:' .. self.jid, 'jid', 'klass', 'state', 'queue',
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

function ReqlessRecurringJob:update(now, ...)
  local options = {}
  if redis.call('exists', 'rql:r:' .. self.jid) ~= 0 then
    for i = 1, #arg, 2 do
      local key = arg[i]
      local value = arg[i+1]
      assert(value, 'No value provided for ' .. tostring(key))
      if key == 'priority' or key == 'interval' or key == 'retries' then
        value = assert(tonumber(value), 'Recur(): Arg "' .. key .. '" must be a number: ' .. tostring(value))
        if key == 'interval' then
          local queue, interval = unpack(redis.call('hmget', 'rql:r:' .. self.jid, 'queue', 'interval'))
          Reqless.queue(queue).recurring.update(
            value - tonumber(interval), self.jid)
        end
        redis.call('hset', 'rql:r:' .. self.jid, key, value)
      elseif key == 'data' then
        assert(cjson.decode(value), 'Recur(): Arg "data" is not JSON-encoded: ' .. tostring(value))
        redis.call('hset', 'rql:r:' .. self.jid, 'data', value)
      elseif key == 'klass' then
        redis.call('hset', 'rql:r:' .. self.jid, 'klass', value)
      elseif key == 'queue' then
        local old_queue_name = redis.call('hget', 'rql:r:' .. self.jid, 'queue')
        local queue_obj = Reqless.queue(old_queue_name)
        local score = queue_obj.recurring.score(self.jid)

        queue_obj.recurring.remove(self.jid)
        local throttles = cjson.decode(redis.call('hget', 'rql:r:' .. self.jid, 'throttles') or '{}')
        for index, throttle_name in ipairs(throttles) do
          if throttle_name == ReqlessQueue.ns .. old_queue_name then
            table.remove(throttles, index)
          end
        end


        table.insert(throttles, ReqlessQueue.ns .. value)
        redis.call('hset', 'rql:r:' .. self.jid, 'throttles', cjson.encode(throttles))

        Reqless.queue(value).recurring.add(score, self.jid)
        redis.call('hset', 'rql:r:' .. self.jid, 'queue', value)
        if redis.call('zscore', 'rql:queues', value) == false then
          redis.call('zadd', 'rql:queues', now, value)
        end
      elseif key == 'backlog' then
        value = assert(tonumber(value),
          'Recur(): Arg "backlog" not a number: ' .. tostring(value))
        redis.call('hset', 'rql:r:' .. self.jid, 'backlog', value)
      elseif key == 'throttles' then
        local throttles = assert(cjson.decode(value), 'Recur(): Arg "throttles" is not JSON-encoded: ' .. tostring(value))
        redis.call('hset', 'rql:r:' .. self.jid, 'throttles', cjson.encode(throttles))
      else
        error('Recur(): Unrecognized option "' .. key .. '"')
      end
    end
    return true
  end

  error('Recur(): No recurring job ' .. self.jid)
end

function ReqlessRecurringJob:tag(...)
  local tags = redis.call('hget', 'rql:r:' .. self.jid, 'tags')
  if tags then
    tags = cjson.decode(tags)
    local _tags = {}
    for _, v in ipairs(tags) do _tags[v] = true end

    for i=1, #arg do if _tags[arg[i]] == nil then table.insert(tags, arg[i]) end end

    tags = cjson.encode(tags)
    redis.call('hset', 'rql:r:' .. self.jid, 'tags', tags)
    return tags
  end

  error('Tag(): Job ' .. self.jid .. ' does not exist')
end

function ReqlessRecurringJob:untag(...)
  local tags = redis.call('hget', 'rql:r:' .. self.jid, 'tags')
  if tags then
    tags = cjson.decode(tags)
    local _tags = {}
    for _, v in ipairs(tags) do _tags[v] = true end
    for i = 1, #arg do _tags[arg[i]] = nil end
    local results = {}
    for _, tag in ipairs(tags) do if _tags[tag] then table.insert(results, tag) end end
    tags = cjson.encode(results)
    redis.call('hset', 'rql:r:' .. self.jid, 'tags', tags)
    return tags
  end

  error('Untag(): Job ' .. self.jid .. ' does not exist')
end

function ReqlessRecurringJob:unrecur()
  local queue = redis.call('hget', 'rql:r:' .. self.jid, 'queue')
  if queue then
    Reqless.queue(queue).recurring.remove(self.jid)
    redis.call('del', 'rql:r:' .. self.jid)
    return true
  end

  return true
end
function ReqlessWorker.deregister(...)
  redis.call('zrem', 'rql:workers', unpack(arg))
end

function ReqlessWorker.counts(now, worker)
  local interval = tonumber(Reqless.config.get('max-worker-age', 86400))

  local workers  = redis.call('zrangebyscore', 'rql:workers', 0, now - interval)
  for _, worker in ipairs(workers) do
    redis.call('del', 'rql:w:' .. worker .. ':jobs')
  end

  redis.call('zremrangebyscore', 'rql:workers', 0, now - interval)

  if worker then
    return {
      jobs    = redis.call('zrevrangebyscore', 'rql:w:' .. worker .. ':jobs', now + 8640000, now),
      stalled = redis.call('zrevrangebyscore', 'rql:w:' .. worker .. ':jobs', now, 0)
    }
  end

  local response = {}
  local workers = redis.call('zrevrange', 'rql:workers', 0, -1)
  for _, worker in ipairs(workers) do
    table.insert(response, {
      name    = worker,
      jobs    = redis.call('zcount', 'rql:w:' .. worker .. ':jobs', now, now + 8640000),
      stalled = redis.call('zcount', 'rql:w:' .. worker .. ':jobs', 0, now)
    })
  end
  return response
end
function ReqlessThrottle:data()
  local data = {
    id = self.id,
    maximum = 0
  }

  local throttle = redis.call('hmget', ReqlessThrottle.ns .. self.id, 'id', 'maximum')

  if throttle[2] then
    data.maximum = tonumber(throttle[2])
  end

  return data
end

function ReqlessThrottle:set(data, expiration)
  redis.call('hmset', ReqlessThrottle.ns .. self.id, 'id', self.id, 'maximum', data.maximum)
  if expiration > 0 then
    redis.call('expire', ReqlessThrottle.ns .. self.id, expiration)
  end
end

function ReqlessThrottle:unset()
  redis.call('del', ReqlessThrottle.ns .. self.id)
end

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

function ReqlessThrottle:release(now, jid)
  if self.locks.remove(jid) == 0 then
    self.pending.remove(jid)
  end

  local available_locks = self:locks_available()
  if self.pending.length() == 0 or available_locks < 1 then
    return
  end

  for _, jid in ipairs(self.pending.peek(0, available_locks - 1)) do
    local job = Reqless.job(jid)
    local data = job:data()
    local queue = Reqless.queue(data['queue'])

    queue.throttled.remove(jid)
    queue.work.add(now, data.priority, jid)
  end

  local popped = self.pending.pop(0, available_locks - 1)
end

function ReqlessThrottle:available()
  return self.maximum == 0 or self.locks.length() < self.maximum
end

function ReqlessThrottle:ttl()
  return redis.call('ttl', ReqlessThrottle.ns .. self.id)
end

function ReqlessThrottle:locks_available()
  if self.maximum == 0 then
    return 10
  end

  return self.maximum - self.locks.length()
end
local ReqlessAPI = {}

ReqlessAPI['config.get'] = function(now, key)
  if key then
    return Reqless.config.get(key)
  end
  return cjson.encode(Reqless.config.get(nil))
end

ReqlessAPI['config.set'] = function(now, key, value)
  return Reqless.config.set(key, value)
end

ReqlessAPI['config.unset'] = function(now, key)
  return Reqless.config.unset(key)
end

ReqlessAPI['job.cancel'] = function(now, ...)
  return Reqless.cancel(now, unpack(arg))
end

ReqlessAPI['job.complete'] = function(now, jid, worker, queue, data, ...)
  return Reqless.job(jid):complete(now, worker, queue, data, unpack(arg))
end

ReqlessAPI['job.depends'] = function(now, jid, command, ...)
  return Reqless.job(jid):depends(now, command, unpack(arg))
end

ReqlessAPI['job.fail'] = function(now, jid, worker, group, message, data)
  return Reqless.job(jid):fail(now, worker, group, message, data)
end

ReqlessAPI['job.get'] = function(now, jid)
  local data = Reqless.job(jid):data()
  if data then
    return cjson.encode(data)
  end
end

ReqlessAPI['job.getMulti'] = function(now, ...)
  local results = {}
  for _, jid in ipairs(arg) do
    table.insert(results, Reqless.job(jid):data())
  end
  return cjson.encode(results)
end

ReqlessAPI['job.heartbeat'] = function(now, jid, worker, data)
  return Reqless.job(jid):heartbeat(now, worker, data)
end

ReqlessAPI['job.log'] = function(now, jid, message, data)
  assert(jid, "Log(): Argument 'jid' missing")
  assert(message, "Log(): Argument 'message' missing")
  if data then
    data = assert(cjson.decode(data),
      "Log(): Argument 'data' not cjson: " .. tostring(data))
  end

  local job = Reqless.job(jid)
  assert(job:exists(), 'Log(): Job ' .. jid .. ' does not exist')
  job:history(now, message, data)
end

ReqlessAPI['job.priority'] = function(now, jid, priority)
  return Reqless.job(jid):priority(priority)
end

ReqlessAPI['job.requeue'] = function(now, worker, queue, jid, ...)
  local job = Reqless.job(jid)
  assert(job:exists(), 'Requeue(): Job ' .. jid .. ' does not exist')
  return ReqlessAPI['queue.put'](now, worker, queue, jid, unpack(arg))
end

ReqlessAPI['job.retry'] = function(now, jid, queue, worker, delay, group, message)
  return Reqless.job(jid):retry(now, queue, worker, delay, group, message)
end

ReqlessAPI['job.tag'] = function(now, jid, ...)
  return cjson.encode(Reqless.tag(now, 'add', jid, unpack(arg)))
end

ReqlessAPI['job.timeout'] = function(now, ...)
  for _, jid in ipairs(arg) do
    Reqless.job(jid):timeout(now)
  end
end

ReqlessAPI['job.track'] = function(now, jid)
  return cjson.encode(Reqless.track(now, 'track', jid))
end

ReqlessAPI['job.untag'] = function(now, jid, ...)
  return cjson.encode(Reqless.tag(now, 'remove', jid, unpack(arg)))
end

ReqlessAPI['job.untrack'] = function(now, jid)
  return cjson.encode(Reqless.track(now, 'untrack', jid))
end

ReqlessAPI["jobs.completed"] = function(now, offset, limit)
  return Reqless.jobs(now, 'complete', offset, limit)
end

ReqlessAPI['jobs.failed'] = function(now, group, start, limit)
  return cjson.encode(Reqless.failed(group, start, limit))
end

ReqlessAPI['jobs.tagged'] = function(now, tag, ...)
  return cjson.encode(Reqless.tag(now, 'get', tag, unpack(arg)))
end

ReqlessAPI['jobs.tracked'] = function(now)
  return cjson.encode(Reqless.track(now))
end

ReqlessAPI['queue.counts'] = function(now, queue)
  return cjson.encode(ReqlessQueue.counts(now, queue))
end

ReqlessAPI['queue.forget'] = function(now, ...)
  ReqlessQueue.deregister(unpack(arg))
end

ReqlessAPI["queue.jobsByState"] = function(now, state, ...)
  return Reqless.jobs(now, state, unpack(arg))
end

ReqlessAPI['queue.length'] = function(now, queue)
  return Reqless.queue(queue):length()
end

ReqlessAPI['queue.pause'] = function(now, ...)
  return ReqlessQueue.pause(now, unpack(arg))
end

ReqlessAPI['queue.peek'] = function(now, queue, offset, count)
  local jids = Reqless.queue(queue):peek(now, offset, count)
  local response = {}
  for _, jid in ipairs(jids) do
    table.insert(response, Reqless.job(jid):data())
  end
  return cjson.encode(response)
end

ReqlessAPI['queue.pop'] = function(now, queue, worker, count)
  local jids = Reqless.queue(queue):pop(now, worker, count)
  local response = {}
  for _, jid in ipairs(jids) do
    table.insert(response, Reqless.job(jid):data())
  end
  return cjson.encode(response)
end

ReqlessAPI['queue.put'] = function(now, worker, queue, jid, klass, data, delay, ...)
  return Reqless.queue(queue):put(now, worker, jid, klass, data, delay, unpack(arg))
end

ReqlessAPI['queue.recur'] = function(now, queue, jid, klass, data, spec, ...)
  return Reqless.queue(queue):recur(now, jid, klass, data, spec, unpack(arg))
end

ReqlessAPI['queue.stats'] = function(now, queue, date)
  return cjson.encode(Reqless.queue(queue):stats(now, date))
end

ReqlessAPI['queue.throttle.get'] = function(now, queue)
  local data = Reqless.throttle(ReqlessQueue.ns .. queue):data()
  if data then
    return cjson.encode(data)
  end
end

ReqlessAPI['queue.throttle.set'] = function(now, queue, max)
  Reqless.throttle(ReqlessQueue.ns .. queue):set({maximum = max}, 0)
end

ReqlessAPI['queue.unfail'] = function(now, queue, group, count)
  return Reqless.queue(queue):unfail(now, group, count)
end

ReqlessAPI['queue.unpause'] = function(now, ...)
  return ReqlessQueue.unpause(unpack(arg))
end

ReqlessAPI['queues.list'] = function(now)
  return cjson.encode(ReqlessQueue.counts(now, nil))
end

ReqlessAPI['recurringJob.get'] = function(now, jid)
  local data = Reqless.recurring(jid):data()
  if data then
    return cjson.encode(data)
  end
end

ReqlessAPI['recurringJob.tag'] = function(now, jid, ...)
  return Reqless.recurring(jid):tag(unpack(arg))
end

ReqlessAPI['recurringJob.unrecur'] = function(now, jid)
  return Reqless.recurring(jid):unrecur()
end

ReqlessAPI['recurringJob.untag'] = function(now, jid, ...)
  return Reqless.recurring(jid):untag(unpack(arg))
end

ReqlessAPI['recurringJob.update'] = function(now, jid, ...)
  return Reqless.recurring(jid):update(now, unpack(arg))
end

ReqlessAPI['tags.top'] = function(now, ...)
  return cjson.encode(Reqless.tag(now, 'top', unpack(arg)))
end

ReqlessAPI['throttle.delete'] = function(now, tid)
  return Reqless.throttle(tid):unset()
end

ReqlessAPI['throttle.get'] = function(now, tid)
  return cjson.encode(Reqless.throttle(tid):data())
end

ReqlessAPI['throttle.locks'] = function(now, tid)
  return Reqless.throttle(tid).locks.members()
end

ReqlessAPI['throttle.pending'] = function(now, tid)
  return Reqless.throttle(tid).pending.members()
end

ReqlessAPI['throttle.release'] = function(now, tid, ...)
  local throttle = Reqless.throttle(tid)

  for _, jid in ipairs(arg) do
    throttle:release(now, jid)
  end
end

ReqlessAPI['throttle.set'] = function(now, tid, max, ...)
  local expiration = unpack(arg)
  local data = {
    maximum = max
  }
  Reqless.throttle(tid):set(data, tonumber(expiration or 0))
end

ReqlessAPI['throttle.ttl'] = function(now, tid)
  return Reqless.throttle(tid):ttl()
end

ReqlessAPI['worker.counts'] = function(now, worker)
  return cjson.encode(ReqlessWorker.counts(now, worker))
end

ReqlessAPI['worker.unregister'] = function(now, ...)
  return ReqlessWorker.deregister(unpack(arg))
end

ReqlessAPI['workers.list'] = function(now)
  return cjson.encode(ReqlessWorker.counts(now, nil))
end


if #KEYS > 0 then error('No Keys should be provided') end

local command_name = assert(table.remove(ARGV, 1), 'Must provide a command')
local command      = assert(
  ReqlessAPI[command_name], 'Unknown command ' .. command_name)

local now          = tonumber(table.remove(ARGV, 1))
local now          = assert(
  now, 'Arg "now" missing or not a number: ' .. (now or 'nil'))

return command(now, unpack(ARGV))
