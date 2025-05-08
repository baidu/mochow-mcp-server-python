# Copyright 2025 Baidu, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file
# except in compliance with the License. You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under the
# License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
# either express or implied. See the License for the specific language governing permissions
# and limitations under the License.

"""
This module integrates with the MCP server framework and offers a suite of tools for interacting with a Mochow instance.
It includes functions for managing databases, tables, and vector indexes, as well as performing searches.
"""
import argparse
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Optional
from dotenv import load_dotenv

from mcp.server.fastmcp import Context, FastMCP

from pymochow import MochowClient
from pymochow.auth.bce_credentials import BceCredentials
from pymochow.configuration import Configuration
from pymochow.exception import ServerError
from pymochow.model.enum import IndexType, MetricType, ServerErrCode
from pymochow.model.schema import HNSWParams, VectorIndex, HNSWPQParams, PUCKParams
from pymochow.model.table import VectorTopkSearchRequest, VectorSearchConfig, FloatVector, BM25SearchRequest
from pymochow.http.http_response import HttpResponse

class MochowConnector:
    """
    A connector class for interacting with a Mochow instance.
    It provides methods for managing databases, tables, and vector indexes.
    """
    def __init__(self, endpoint: str, api_key: Optional[str] = None):
        """
        Initialize the MochowConnector.

        Args:
            endpoint (str): The endpoint of the Mochow instance.
            api_key (Optional[str]): The API key for authentication. Defaults to None.
        """
        self.endpoint = endpoint
        self.api_key = api_key
        config = Configuration(credentials=BceCredentials("root", api_key), endpoint=endpoint)
        self.client = MochowClient(config)

    async def list_databases(self) -> list[str]:
        """
        List all databases in the Mochow instance.

        Returns:
            list[str]: A list of database names.
        """
        try:
            databases = self.client.list_databases()
            return [database.database_name for database in databases]
        except Exception as e:
            raise ValueError(f"Failed to list databases: {str(e)}")

    async def create_database(self, db_name: str) -> bool:
        """
        Create a new database.

        Args:
            db_name (str): Name of the database to create.

        Returns:
            bool: True if the database is created or already exists, False otherwise.
        """
        try:
            # database already existed
            for db in self.client.list_databases():
                if db.database_name == db_name:
                    return True

            # create the new database
            self.client.create_database(db_name)
            self.database = self.client.database(db_name)
            return True
        except Exception as e:
            raise ValueError(f"Failed to create database: {str(e)}")

    async def use_database(self, db_name: str) -> bool:
        """
        Switch to a different database.

        Args:
            db_name (str): Name of the database to use.

        Returns:
            bool: True if the database switch is successful, False otherwise.
        """
        try:
            self.database = self.client.database(db_name)
            return True
        except Exception as e:
            raise ValueError(f"Failed to switch database: {str(e)}")

    async def list_tables(self) -> list[str]:
        """
        List all tables in the current database.

        Returns:
            list[str]: A list of table names.
        """
        if self.database is None:
            raise ValueError("Switch to the database before list tables")
        try:
            tables = self.database.list_table()
            return [table.table_name for table in tables]
        except Exception as e:
            raise ValueError(f"Failed to list tables: {str(e)}")

    async def describe_table_info(self, table_name: str) -> dict:
        """
        Get detailed information about a table.

        Args:
            table_name (str): Name of the table.

        Returns:
            dict: A dictionary containing table details.
        """
        if self.database is None:
            raise ValueError("Switch to the database before describe table")
        try:
            return self.database.describe_table(table_name).to_dict()
        except Exception as e:
            raise ValueError(f"Failed to get table detail info: {str(e)}")

    async def get_table_statistics(self, table_name: str) -> HttpResponse:
        """
        Get statistics information about a table.

        Args:
            table_name (str): Name of the table.

        Returns:
            HttpResponse: The HTTP response containing the table statistics.
        """
        if self.database is None:
            raise ValueError("Switch to the database before get table statistics")
        try:
            return self.database.table(table_name).stats()
        except Exception as e:
            raise ValueError(f"Failed to get table statistics: {str(e)}")

    async def describe_index_info(self, table_name: str, index_name: str) -> dict:
        """
        Get detailed information about a index.

        Args:
            table_name (str): Name of the table.
            index_name (str): Name of the index.

        Returns:
            dict: A dictionary containing index details.
        """
        if self.database is None:
            raise ValueError("Switch to the database before describe index")
        try:
            return self.database.table(table_name).describe_index(index_name).to_dict()
        except Exception as e:
            raise ValueError(f"Failed to get index detail info: {str(e)}")

    async def create_vector_index(
        self,
        table_name: str,
        index_name: str,
        field_name: str,
        index_type: str = "HNSW",
        metric_type: str = "L2",
        params: Optional[dict[str, Any]] = None,
    ) -> bool:
        """
        Create a vector index on a given vector field.

        Args:
            table_name (str): Name of the table.
            index_name (str): Name of the index.
            field_name (str): Name of the vector field.
            index_type (str): Type of vector index. Supported values are "HNSW", "HNSWPQ", "PUCK".
            metric_type (str): Distance metric. Supported values are "L2", "COSINE", "IP".
            params (Optional[dict[str, Any]]): Additional vector index parameters.

        Returns:
            bool: True if the index is created successfully, False otherwise.
        """
        if self.database is None:
            raise ValueError("Switch to the database before create vector index")

        # check vector index
        index_existed = True
        try:
            self.database.table(table_name).describe_index(index_name)
        except ServerError as e:
            if e.code == ServerErrCode.INDEX_NOT_EXIST:
                index_existed = False
            else:
                raise ValueError(f"Failed to get index detail: {str(e)}")

        # index already existed with same name
        if index_existed:
            raise ValueError(f"Index already existed with same name '{index_name}'")

        # create vector index
        index_metric_type = None
        for k, v in MetricType.__members__.items():
            if k == metric_type:
                index_metric_type = v
        if index_metric_type is None:
            raise ValueError("Only the three metric types of L2, COSINE, and IP are supported.")

        indexes = []
        if index_type == "HNSW":
            indexes.append(
                VectorIndex(
                    index_name=index_name, index_type=IndexType.HNSW, field=field_name,
                    metric_type=index_metric_type, auto_build=False,
                    params=HNSWParams(m=params.get("M", 16), efconstruction=params.get("efConstruction", 200))))
        elif index_type == "HNSWPQ":
            indexes.append(
                VectorIndex(
                    index_name=index_name, index_type=IndexType.HNSW, field=field_name,
                    metric_type=index_metric_type, auto_build=False,
                    params=HNSWPQParams(
                        m=params.get("M", 16), efconstruction=params.get("efConstruction", 200),
                        NSQ=params.get("NSQ", 8), samplerate=params.get("sampleRate", 1.0))))
        elif index_type == "PUCK":
            indexes.append(
                VectorIndex(
                    index_name=index_name, index_type=IndexType.HNSW, field=field_name,
                    metric_type=index_metric_type, auto_build=False,
                    params=PUCKParams(
                        coarseClusterCount=params.get("coarseClusterCount", 5),
                        fineClusterCount=params.get("fineClusterCount", 5))))
        else:
            raise ValueError("Only the three vector index types of HNSW, HNSWPQ, PUCK are supported.")

        try:
            self.database.table(table_name).create_indexes(indexes)
            return True
        except Exception as e:
            raise ValueError(f"Failed to create vector index: {str(e)}")

    async def rebuild_vector_index(self, table_name: str, index_name: str) -> bool:
        """
        Rebuild a vector index in a given table.

        Args:
            table_name (str): Name of the table.
            index_name (str): Name of the vector index.

        Returns:
            bool: True if the index is rebuilt successfully, False otherwise.
        """
        if self.database is None:
            raise ValueError("Switch to the database before rebuild vector index")

        # check vector index
        index_existed = True
        try:
            self.database.table(table_name).describe_index(index_name)
        except ServerError as e:
            if e.code == ServerErrCode.INDEX_NOT_EXIST:
                index_existed = False
            else:
                raise ValueError(f"Failed to get index detail: {str(e)}")

        # index already existed with same name
        if not index_existed:
            raise ValueError(f"Vector index not existed with name '{index_name}'")

        try:
            self.database.table(table_name).rebuild_index(index_name)
            return True
        except Exception as e:
            raise ValueError(f"Failed to rebuild vector index: {str(e)}")

    async def drop_vector_index(self, table_name: str, index_name: str) -> bool:
        """
        Drop a vector index in a given table.

        Args:
            table_name (str): Name of the table.
            index_name (str): Name of the vector index.

        Returns:
            bool: True if the index is dropped successfully or does not exist, False otherwise.
        """
        if self.database is None:
            raise ValueError("Switch to the database before drop vector index")

        # check vector index
        index_existed = True
        try:
            self.database.table(table_name).describe_index(index_name)
        except ServerError as e:
            if e.code == ServerErrCode.INDEX_NOT_EXIST:
                index_existed = False
            else:
                raise ValueError(f"Failed to get index detail: {str(e)}")

        # index already existed with same name
        if not index_existed:
            return True
        try:
            self.database.table(table_name).drop_index(index_name)
            return True
        except Exception as e:
            raise ValueError(f"Failed to drop vector index: {str(e)}")

    async def select_rows(
        self,
        table_name: str,
        filter_expr: str = None,
        limit: int = 10,
        output_fields: Optional[list[str]] = None,
    ) -> HttpResponse:
        """
        Select rows in a given table using a filter expression.

        Args:
            table_name (str): Name of the table.
            filter_expr (str): Filter expression to select data.
            limit (int): Maximum number of results. Defaults to 10.
            output_fields (Optional[list[str]]): Fields to return in the results. Defaults to None.

        Returns:
            HttpResponse: The HTTP response containing the selected rows.
        """
        if self.database is None:
            raise ValueError("Switch to the database before select rows with filter expression.")

        # select data with filter expression
        try:
            return self.database.table(table_name).select(filter=filter_expr, projections=output_fields, limit=limit)
        except ServerError as e:
            raise ValueError(f"Failed to select data with filter expression: {str(e)}")

    async def delete_rows(self, table_name: str, filter_expr: str) -> bool:
        """
        Delete rows in a given table using a filter expression.

        Args:
            table_name (str): Name of the table.
            filter_expr (str): Filter expression to select data to delete.

        Returns:
            bool: True if the rows is deleted successfully, False otherwise.
        """
        if self.database is None:
            raise ValueError("Switch to the database before delete rows with filter expression.")

        try:
            self.database.table(table_name).delete(filter=filter_expr)
            return True
        except Exception as e:
            raise ValueError(f"Failed to delete data with filter expression: {filter_expr}")

    async def vector_search(
        self,
        table_name: str, 
        vector: list[float],
        vector_field: str = "vector",
        limit: int = 10,
        output_fields: Optional[list[str]] = None,
        filter_expr: Optional[str] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> HttpResponse:
        """
        Perform vector similarity search combining vector similarity and scalar attribute filtering.

        Args:
            table_name (str): Name of the table to search.
            vector (list[float]): Search vector.
            vector_field (str): Target field containing vectors to search. Defaults to "vector".
            limit (int): Maximum number of results. Defaults to 10.
            output_fields (Optional[list[str]]): Fields to return in the results. Defaults to None.
            filter_expr (Optional[str]): Filter expression for scalar attributes. Defaults to None.
            params (Optional[dict[str, Any]]): Additional vector search parameters. Defaults to None.

        Returns:
            HttpResponse: The HTTP response containing the search results.
        """
        if self.database is None:
            raise ValueError("Switch to the database before perform vector search.")

        request = VectorTopkSearchRequest(vector_field=vector_field, vector=FloatVector(vector),
                                          limit=limit, filter=filter_expr,
                                          config=VectorSearchConfig(ef=params.get("ef", 200)))
        try:
            return self.database.table(table_name).vector_search(request=request, projections=output_fields)
        except Exception as e:
            raise ValueError(f"Failed to perform vector search: {str(e)}")

    async def fulltext_search(
        self,
        table_name: str, 
        index_name: str,
        search_text: str,
        limit: int = 10,
        output_fields: Optional[list[str]] = None,
        filter_expr: Optional[str] = None,
    ) -> HttpResponse:
        """
        Perform full text search combining BM25 similarity and scalar attribute filtering.

        Args:
            table_name (str): Name of the table to search.
            index_name (str): Name of the inverted index to perform full text search.
            search_text (str): Text to search.
            limit (int): Maximum number of results. Defaults to 10.
            output_fields (Optional[list[str]]): Fields to return in the results. Defaults to None.
            filter_expr (Optional[str]): Filter expression for scalar attributes. Defaults to None.

        Returns:
            HttpResponse: The HTTP response containing the search results.
        """
        if self.database is None:
            raise ValueError("Switch to the database before perform full text search.")

        request = BM25SearchRequest(index_name=index_name,
                                    search_text=search_text,
                                    limit=limit,
                                    filter=filter_expr)
        try:
            return self.database.table(table_name).bm25_search(request=request, projections=output_fields)
        except Exception as e:
            raise ValueError(f"Failed to perform full text search: {str(e)}")

class MochowContext:
    """
    A context class that holds a MochowConnector instance.
    """
    def __init__(self, connector: MochowConnector):
        """
        Initialize the MochowContext.

        Args:
            connector (MochowConnector): A MochowConnector instance.
        """
        self.connector = connector

@asynccontextmanager
async def server_lifespan(server: FastMCP) -> AsyncIterator[MochowContext]:
    """
    Manage application lifecycle for Mochow connector.

    Args:
        server (FastMCP): A FastMCP server instance.

    Yields:
        MochowContext: A MochowContext instance containing a MochowConnector.
    """
    config = server.config

    connector = MochowConnector(
        endpoint=config.get("endpoint", "http://localhost:8287"),
        api_key=config.get("api_key"),
    )

    try:
        yield MochowContext(connector)
    finally:
        pass

mcp = FastMCP("Mochow", lifespan=server_lifespan)

@mcp.tool()
async def list_databases(ctx: Context = None) -> str:
    """
    List all databases in the Mochow instance.

    Returns:
        str: A string containing the names of all databases.
    """
    connector = ctx.request_context.lifespan_context.connector
    databases = await connector.list_databases()
    return f"Databases in Mochow instance:\n{', '.join(databases)}"

@mcp.tool()
async def create_database(database_name: str, ctx: Context = None) -> str:
    """
    Create a database in the Mochow instance.

    Args:
        database_name (str): Name of the database.

    Returns:
        str: A message indicating the success of database creation.
    """
    connector = ctx.request_context.lifespan_context.connector
    await connector.create_database(database_name)
    return f"Created a database named '{database_name}'in Mochow instance:\n"

@mcp.tool()
async def use_database(database_name: str, ctx: Context = None) -> str:
    """
    Switch to a different database.

    Args:
        database_name (str): Name of the database to use.

    Returns:
        str: A message indicating the success of the database switch.
    """
    connector = ctx.request_context.lifespan_context.connector
    await connector.use_database(database_name)
    
    return f"Switched to database '{database_name}' successfully"

@mcp.tool()
async def list_tables(ctx: Context) -> str:
    """
    List all tables in the current database.

    Returns:
        str: A string containing the names of all tables.
    """
    connector = ctx.request_context.lifespan_context.connector
    tables = await connector.list_tables()
    return f"Tables in database:\n{', '.join(tables)}"

@mcp.tool()
async def describe_table(table_name: str, ctx: Context = None) -> str:
    """
    Describe table details in the Mochow instance.

    Args:
        table_name (str): Name of the table to describe.

    Returns:
        str: A string containing the details of the table.
    """
    connector = ctx.request_context.lifespan_context.connector
    details = await connector.describe_table_info(table_name)
    return f"Table details named '{table_name}' in Mochow instance:\n{str(details)}"

@mcp.tool()
async def stats_table(table_name: str, ctx: Context = None) -> str:
    """
    Get the table statistics in the Mochow instance.

    Args:
        table_name (str): Name of the table to get statistics.

    Returns:
        str: A string containing the table statistics.
    """
    connector = ctx.request_context.lifespan_context.connector
    stats = await connector.get_table_statistics(table_name)
    output = f"Table statistics named '{table_name}' in Mochow instance:\n"
    output += f"TotalRowCount: {str(stats.row_count)}\n"
    output += f"MemorySizeInByte: {str(stats.memory_size_in_byte)}\n"
    output += f"DiskSizeInByte: {str(stats.disk_size_in_byte)}\n"
    return output

@mcp.tool()
async def create_vector_index(
    table_name: str,
    index_name: str,
    field_name: str,
    index_type: str = "HNSW",
    metric_type: str = "L2",
    params: Optional[dict[str, Any]] = None,
    ctx: Context = None) -> str:
    """
    Create a vector index on a vector type field in the Mochow instance.

    Args:
        table_name (str): Name of the table.
        index_name (str): Name of the index.
        field_name (str): Name of the vector field.
        index_type (str): Type of vector index. Supported values are "HNSW", "HNSWPQ", "HNSWSQ".
        metric_type (str): Distance metric. Supported values are "L2", "COSINE", "IP".
        params (Optional[dict[str, Any]]): Additional vector index parameters.

    Returns:
        str: A message indicating the success of index creation.
    """
    connector = ctx.request_context.lifespan_context.connector
    await connector.create_vector_index(table_name, index_name, field_name, index_type, metric_type, params)
    return f"Vector index '{index_name}' created successfully"

@mcp.tool()
async def describe_index(table_name: str, index_name: str, ctx: Context = None) -> str:
    """
    Describe index details in the Mochow instance.

    Args:
        table_name (str): Name of the table.
        index_name (str): Name of the index to describe.

    Returns:
        str: A string containing the details of the index.
    """
    connector = ctx.request_context.lifespan_context.connector
    details = await connector.describe_index_info(table_name, index_name)
    return f"Index details named '{index_name}' for table named '{table_name}' in Mochow instance:\n{str(details)}"

@mcp.tool()
async def rebuild_vector_index(table_name: str, index_name: str, ctx: Context = None) -> str:
    """
    Rebuild the vector index in the Mochow instance.

    Args:
        table_name (str): Name of the table.
        index_name (str): Name of the vector index to rebuild.

    Returns:
        str: A message indicating the success of index rebuild initiation.
    """
    connector = ctx.request_context.lifespan_context.connector
    await connector.rebuild_vector_index(table_name, index_name)
    return f"Initiate the rebuild of vector index '{index_name}' successfully."

@mcp.tool()
async def delete_table_rows(table_name: str, filter_expr: str, ctx: Context = None) -> str:
    """
    Delete rows with a filter expression in the Mochow instance.

    Args:
        table_name (str): Name of the table.
        filter_expr (str): Filter expression to select data to delete.

    Returns:
        str: A message indicating the success of data deletion.
    """
    connector = ctx.request_context.lifespan_context.connector
    await connector.delete_rows(table_name, filter_expr)
    return f"Delete rows with filter expression '{filter_expr}' successfully."

@mcp.tool()
async def drop_vector_index(table_name: str, index_name: str, ctx: Context = None) -> str:
    """
    Drop the vector index in the Mochow instance.

    Args:
        table_name (str): Name of the table.
        index_name (str): Name of the vector index to drop.

    Returns:
        str: A message indicating the success of index drop.
    """
    connector = ctx.request_context.lifespan_context.connector
    await connector.drop_vector_index(table_name, index_name)
    return f"Drop the vector index '{index_name}' successfully."

@mcp.tool()
async def select_table_rows(
    table_name: str,
    filter_expr: str = None, 
    limit: int = 10,
    output_fields: Optional[list[str]] = None,
    ctx: Context = None,
) -> str:
    """
    Select rows with a filter expression in the Mochow instance.

    Args:
        table_name (str): Name of the table.
        filter_expr (str): Filter expression to select data. Defaults to None.
        limit (int): Maximum number of results. Defaults to 10.
        output_fields (Optional[list[str]]): Fields to return in the results. Defaults to None.

    Returns:
        str: A string containing the selected rows.
    """
    connector = ctx.request_context.lifespan_context.connector
    select_results = await connector.select_rows(table_name, filter_expr, limit, output_fields)
    output = f"Select rows results for '{table_name}':\n"
    for row in select_results.rows:
        output += f"{str(row)}\n"
    return output

@mcp.tool()
async def vector_search(
    table_name: str, 
    vector: list[float],
    vector_field: str = "vector",
    filter_expr: Optional[str] = None,
    limit: int = 10,
    output_fields: Optional[list[str]] = None,
    ctx: Context = None,
) -> str:
    """
    Perform vector similarity search combining vector similarity and scalar attribute filtering in the Mochow instance.

    Args:
        table_name (str): Name of the table to search.
        vector (list[float]): Search vector.
        vector_field (str): Target field containing vectors to search. Defaults to "vector".
        limit (int): Maximum number of results. Defaults to 10.
        output_fields (Optional[list[str]]): Fields to return in the results. Defaults to None.
        filter_expr (Optional[str]): Filter expression for scalar attributes. Defaults to None.
        params: Additional vector search parameters

    Returns:
        str: A string containing the vector search results.
    """
    connector = ctx.request_context.lifespan_context.connector
    search_results = await connector.vector_search(table_name, vector, vector_field, limit, output_fields, filter_expr)

    output = f"Vector search results for '{table_name}':\n"
    for row in search_results.rows:
        output += f"{str(row["row"])}\n"

    return output

@mcp.tool()
async def fulltext_search(
    table_name: str, 
    index_name: str,
    search_text: str,
    filter_expr: Optional[str] = None,
    limit: int = 10,
    output_fields: Optional[list[str]] = None,
    ctx: Context = None,
) -> str:
    """
    Perform full text search combining BM25 similarity and scalar attribute filtering in the Mochow instance.

    Args:
        table_name (str): Name of the table to search.
        index_name (str): Name of the inverted index to perform full text search.
        search_text (str): Text to search.
        limit (int): Maximum number of results. Defaults to 10.
        output_fields (Optional[list[str]]): Fields to return in the results. Defaults to None.

    Returns:
        str: A string containing the full text search results.
    """
    connector = ctx.request_context.lifespan_context.connector
    search_results = await connector.fulltext_search(table_name, index_name, search_text, limit, output_fields, filter_expr)

    output = f"Full text search results for '{table_name}':\n"
    for row in search_results.rows:
        output += f"{str(row["row"])}\n"

    return output

def parse_arguments():
    """Parse arguments from command line."""
    parser = argparse.ArgumentParser(description="Mochow MCP Server")
    parser.add_argument("--endpoint", type=str, default="http://127.0.0.1:8287", help="Mochow server endpoint")
    parser.add_argument("--api-key", type=str, default="mochow", help="Mochow authentication api key")
    return parser.parse_args()

def main():
    """Main entry point for the mcp server."""
    load_dotenv()
    args = parse_arguments()
    mcp.config = {
        "endpoint": os.environ.get("MOCHOW_ENDPOINT", args.endpoint),
        "api_key": os.environ.get("MOCHOW_API_KEY", args.api_key),
    }
    mcp.run()

if __name__ == "__main__":
    main()
