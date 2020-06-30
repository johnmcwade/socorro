# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import contextlib
import datetime
import re

from configman import Namespace, RequiredConfig
from configman.converters import list_converter
import elasticsearch

from socorro.external.es.super_search_fields import SuperSearchFields
from socorro.lib.datetimeutil import utc_now


# Elasticsearch indices configuration.
ES_CUSTOM_ANALYZERS = {
    "analyzer": {"semicolon_keywords": {"type": "pattern", "pattern": ";"}}
}
ES_QUERY_SETTINGS = {"default_field": "signature"}


class ConnectionContext(RequiredConfig):
    """Elasticsearch connection manager.

    Used for accessing Elasticsearch and managing indexes.

    """

    required_config = Namespace()
    required_config.add_option(
        "elasticsearch_urls",
        default=["http://localhost:9200"],
        doc="the urls to the elasticsearch instances",
        from_string_converter=list_converter,
        reference_value_from="resource.elasticsearch",
    )
    required_config.add_option(
        "elasticsearch_timeout",
        default=30,
        doc="the time in seconds before a query to elasticsearch fails",
        reference_value_from="resource.elasticsearch",
    )
    required_config.add_option(
        "elasticsearch_timeout_extended",
        default=120,
        doc="the time in seconds before a query to elasticsearch fails in "
        "restricted sections",
        reference_value_from="resource.elasticsearch",
    )
    required_config.add_option(
        "elasticsearch_index",
        default="socorro%Y%W",
        doc=(
            "template for generating index names--use datetime's strftime "
            "format to have daily, weekly or monthly indexes"
        ),
        reference_value_from="resource.elasticsearch",
    )
    required_config.add_option(
        "elasticsearch_index_regex",
        doc="regex that matches indexes--this should match elasticsearch_index",
        default="^socorro[0-9]{6}$",
        reference_value_from="resource.elasticsearch",
    )
    required_config.add_option(
        "retention_policy",
        default=26,
        doc="number of weeks to retain an index",
        reference_value_from="resource.elasticsearch",
    )
    required_config.add_option(
        "elasticsearch_doctype",
        default="crash_reports",
        doc="the default doctype to use in elasticsearch",
        reference_value_from="resource.elasticsearch",
    )
    required_config.add_option(
        "elasticsearch_shards_per_index",
        default=10,
        doc=(
            "number of shards to set in newly created indices. Elasticsearch "
            "default is 5."
        ),
    )

    def __init__(self, config):
        super().__init__()
        self.config = config

    def connection(self, name=None, timeout=None):
        """Returns an instance of elasticsearch-py's Elasticsearch class as
        encapsulated by the Connection class above.

        Documentation: http://elasticsearch-py.readthedocs.org

        """
        if timeout is None:
            timeout = self.config.elasticsearch_timeout

        return elasticsearch.Elasticsearch(
            hosts=self.config.elasticsearch_urls,
            timeout=timeout,
            connection_class=elasticsearch.connection.RequestsHttpConnection,
            verify_certs=True,
        )

    def get_index_template(self):
        """Return template for index names."""
        return self.config.elasticsearch_index

    def get_doctype(self):
        """Return doctype."""
        return self.config.elasticsearch_doctype

    def get_timeout_extended(self):
        """Return timeout_extended."""
        return self.config.elasticsearch_timeout_extended

    def indices_client(self, name=None):
        """Returns an instance of elasticsearch-py's Index client class as
        encapsulated by the Connection class above.

        http://elasticsearch-py.readthedocs.org/en/latest/api.html#indices

        """
        return elasticsearch.client.IndicesClient(self.connection())

    @contextlib.contextmanager
    def __call__(self, name=None, timeout=None):
        conn = self.connection(name, timeout)
        yield conn

    def get_socorro_index_settings(self, mappings):
        """Return a dictionary containing settings for an Elasticsearch index.
        """
        return {
            "settings": {
                "index": {
                    "number_of_shards": self.config.elasticsearch_shards_per_index,
                    "query": ES_QUERY_SETTINGS,
                    "analysis": ES_CUSTOM_ANALYZERS,
                }
            },
            "mappings": mappings,
        }

    def create_index(self, index_name, mappings=None):
        """Create an index that will receive crash reports.

        :arg index_name: the name of the index to create
        :arg mappings: dict of doctype->ES mapping

        :returns: True if the index was created, False if it already
            existed

        """
        if mappings is None:
            mappings = SuperSearchFields(context=self).get_mapping()

        es_settings = self.get_socorro_index_settings(mappings)

        try:
            client = self.indices_client()
            client.create(index=index_name, body=es_settings)
            return True

        except elasticsearch.exceptions.RequestError as e:
            # If this index already exists, swallow the error.
            # NOTE! This is NOT how the error looks like in ES 2.x
            if "IndexAlreadyExistsException" not in str(e):
                raise
            return False

    def get_indices(self):
        """Return list of existing crash report indices."""
        indices_client = self.indices_client()
        index_regex = re.compile(self.config.elasticsearch_index_regex, re.I)

        status = indices_client.status()
        indices = [
            index for index in status["indices"].keys() if index_regex.match(index)
        ]
        indices.sort()
        return indices

    def delete_index(self, index_name):
        """Delete an index."""
        self.indices_client().delete(index_name)

    def delete_expired_indices(self):
        """Delete indices that exceed our retention policy.

        :returns: list of index names that were deleted

        """
        policy = datetime.timedelta(weeks=self.config.retention_policy)
        cutoff = (utc_now() - policy).replace(tzinfo=None)

        was_deleted = []
        for index_name in self.get_indices():
            # strptime ignores week numbers if a day isn't specified, so we append
            # '-1' and '-%w' to specify Monday as the day.
            index_date = datetime.datetime.strptime(
                index_name + "-1", self.config.elasticsearch_index + "-%w"
            )
            if index_date >= cutoff:
                continue

            self.delete_index(index_name)
            was_deleted.append(index_name)

        return was_deleted

    def refresh(self, index_name=None):
        self.indices_client().refresh(index=index_name or "_all")

    def health_check(self):
        with self() as conn:
            conn.cluster.health(wait_for_status="yellow", request_timeout=5)
