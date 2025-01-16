import zmodels


def setup(env):
    request = env['request']

    # start a transaction
    request.tm.begin()

    # inject some vars into the shell builtins
    env['tm'] = request.tm
    env['models'] = zmodels
