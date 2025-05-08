# 百度向量数据库MCP Server

本代码仓库包含一个 MCP 服务器，它提供对[百度云向量数据库](https://cloud.baidu.com/doc/VDB/index.html)功能的访问。

## 前提条件

在使用百度云向量数据库MCP Server之前，请确保你具备以下条件：
1. Python 3.10 或更高版本
2. 已安装[uv](https://github.com/astral-sh/uv)用于运行MCP Server

## 使用方式

使用百度云向量数据库MCP Server的推荐方式是通过`uv`运行，而无需进行安装。

克隆代码仓库，执行以下命令：
```
git clone https://github.com/baidu/mochow-mcp-server-python.git
cd mochow-mcp-server-python
```
随后，你可以直接通过`uv`运行，其中`endpoint`和`api-key`根据实际需要修改：
```
uv run src/mochow_mcp_server/server.py 
uv run src/mochow_mcp_server/server.py --endpoint http://127.0.0.1:8287 --api-key mochow
```

或者，在`src/mochow_mcp_server/`目录中修改`.env`文件来设置环境变量，再使用以下命令运行服务器：
```
uv run src/mochow_mcp_server/server.py 
```

## 支持的应用程序

百度云向量数据库MCP Server可以与各种支持模型上下文协议的大语言模型应用程序配合使用：

- **Claude Desktop**：Anthropic 公司为 Claude 开发的桌面应用程序

- **Cursor**：支持 MCP 的人工智能代码编辑器

- **自定义 MCP 客户端**：任何实现 MCP 客户端规范的应用程序

## 在Claude Desktop中的使用方式

从[https://claude.ai](https://claude.ai/download)下载 Claude Desktop。

打开 Claude Desktop 的配置文件，在 macOS 系统中，路径为`~/Library/Application Support/Claude/claude_desktop_config.json`。

添加以下配置：
```JSON
{
    "mcpServers": {
        "mochow": {
            "command": "/PATH/TO/uv",
            "args": [
                "--directory",
                "/path/to/mochow-mcp-server-python/src/mochow_mcp_server",
                "run",
                "server.py",
                "--endpoint",
                "http://127.0.0.1:8287",
                "--api-key",
                "mochow"
            ]
        }
    }
}
```
重启 Claude Desktop。

## 在 Cursor 中的使用方法

[Cursor 也支持 MCP](https://docs.cursor.com/context/model-context-protocol)工具。你可以通过两种方式将百度MCP Server添加到Cursor中：

依次打开`Cursor设置`>`功能`>`MCP`，点击`+添加新的MCP服务器`按钮，在`mcp.json`中添加以下配置：
```JSON
{
    "mcpServers": {
        "mochow": {
            "command": "/PATH/TO/uv",
            "args": [
                "--directory",
                "/path/to/mochow-mcp-server-python/src/mochow_mcp_server",
                "run",
                "server.py",
                "--endpoint",
                "http://127.0.0.1:8287",
                "--api-key",
                "mochow"
            ]
        }
    }
}
```
重启 Cursor 或重新加载窗口。

## 可用工具

百度云向量数据库MCP Server提供以下工具：

### Database操作

- `list_databases`: 列出数据库中所有的Database

- `create_database`: 创建一个新的Database

  - 参数：
    - `database_name`: 待创建的Database名称

- `use_database`: 切换到一个已存在的Database

  - 参数：
    - `database_name`: 待切换的Database名称

### Table操作

- `list_tables`: 列出数据库中所有的Table

- `describe_table`: 获取指定Table的详细信息

  - 参数：
    - `table_name`: Table名称

- `stats_table`: 获取指定Table的统计信息

  - 参数：
    - `table_name`: Table名称

### 数据操作

- `delete_table_rows`: 使用过滤表达式删除数据

  - 参数：
    - `table_name`: Table名称
    - `filter_expr`: 过滤表达式

- `select_table_rows`: 使用过滤表达式查询数据

  - 参数：
    - `table_name`: Table名称
    - `filter_expr`: 过滤表达式
    - `limit`: 查询结果的最大条数
    - `output_fields`: 查询结果中要返回的字段名

### 索引操作

- `create_vector_index`: 在指定向量字段上创建向量索引

  - 参数：
    - `table_name`: Table名称
    - `index_name`: 向量索引名称
    - `field_name`: 向量字段名称
    - `index_type`: 向量索引类型
    - `metric_type`: 向量索引的距离度量
    - `params`: 向量索引的创建参数

- `rebuild_vector_index`: 重新构建指定向量索引

  - 参数：
    - `table_name`: Table名称
    - `index_name`: 向量索引名称

- `drop_vector_index`: 删除指定向量索引

  - 参数：
    - `table_name`: Table名称
    - `index_name`: 向量索引名称

- `describe_index`: 获取指定索引的详情信息

  - 参数：
    - `table_name`: Table名称
    - `index_name`: 向量索引名称

### 检索操作

- `vector_search`: 执行带标量过滤的向量相似性检索

  - 参数：
    - `table_name`: Table名称
    - `vector`: 向量
    - `vector_field`: 向量字段名称
    - `limit`: 相似性检索结果中返回最接近目标向量的记录数量
    - `filter_expr`: 过滤表达式
    - `output_fields`: 查询结果中要返回的字段名

- `fulltext_search`: 执行全文检索

  - 参数：
    - `table_name`: Table名称
    - `index_name`: 向量索引名称
    - `search_text`: 全文检索的检索表达式
    - `limit`: 全文检索返回相关性最高的条目数
    - `filter_expr`: 过滤表达式
    - `output_fields`: 查询结果中要返回的字段名

## 环境变量

- `MOCHOW_ENDPOINT`: 百度云向量数据库连接实例URI
- `MOCHOW_API_KEY`: 百度云向量数据库实例API密钥

## 使用样例

### 使用Claude Desktop

#### Example 1: 列出数据库中所有的Database

```
How many databases do i have in the mochow db?
```
Claude将使用百度云向量数据库MCP Server提供的list_databases来获取数据库列表.

```
Let me check how many databases you have in the Mochow instance.

You have 2 databases in your Mochow instance:

1. book
2. test
```

#### Example 2: 查看指定表的schema信息

```
I want to get the detail of  table named book_segments in database book.
```

Claude将使用百度云向量数据库MCP Server提供的describe_table来获取表的详情信息.

```
I'll help you get the details of the "book_segments" table in the "book" database. Let me first switch to the "book" database and then describe the table.

Here's the information about the "book_segments" table in the "book" database:

Database: book
Table Name: book_segments
Creation Time: 2025-05-06 11:08:22
State: NORMAL

Schema:

id (STRING)
Primary Key: Yes
Partition Key: Yes
Not Null: Yes

bookName (STRING)
Not Null: Yes

author (STRING)
Not Null: No

page (UINT32)
Not Null: No

segment (TEXT)
Not Null: No

vector (FLOAT_VECTOR)
Not Null: Yes
Dimension: 1024

Indexes
book_name_filtering_idx (FILTERING_INDEX)
Field: bookName
Order: ASCEND
Structure Type: DEFAULT

vector_idx (HNSW)
Field: vector
Metric Type: L2
Auto Build: False
Parameters: (M: 16 efConstruction: 200)
```