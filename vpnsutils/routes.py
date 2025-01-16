import pyramid.config


def includeme(config: pyramid.config.Configurator):
    config.add_static_view('static', 'static', cache_max_age=3600)
