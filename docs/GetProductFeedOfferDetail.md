-   [Open API Platform](https://affiliate.shopee.com.br/open_api/home)
-   [API List](https://affiliate.shopee.com.br/open_api/list)
-   [Open API Document](https://affiliate.shopee.com.br/open_api/document?type=overview)Must Read

## Get Product Feed Offer Details

Query: `getItemFeedData`

ResultType: `ItemFeedDataConnection!`

Query parameters

| 
Field

 | 

Type

 | 

Description

 | 

Example

 |
| --- | --- | --- | --- |
| datafeedId | String! | 

A unique identifier returned by the listItemFeeds API, used to track specific data snapshots  
Format: {datafeedId}\_{feedMode}\_{grassDate}

 | 12345\_FULL\_20260205 |
| offset | Int | The starting point (index) from which to begin retrieving the current request's results | 0 |
| limit | Int | The number of items to download per page; maximum allowed value is 500 | 500 |

Response parameters

| 
Field

 | 

Type

 | 

Description

 | 

Example

 |
| --- | --- | --- | --- |
| rows | \[ItemFeedDataRow!\]! | Data List |  |
| pageInfo | ItemFeedPageInfo! | Page Information |  |

ItemFeedDataRow structure

| 
Field

 | 

Type

 | 

Description

 | 

Example

 |
| --- | --- | --- | --- |
| columns | String | Core data fields. JSON object strings containing column names and column values |  |
| updateType | DeltaDataUpdateType | Only valid in DELTA mode. Indicates the change type of the record: NEW (new), UPDATE, DELETE. | NEW |

ItemFeedPageInfo structure

| 
Field

 | 

Type

 | 

Description

 | 

Example

 |
| --- | --- | --- | --- |
| offset | Int64! | The starting index for the current data segment | 0 |
| limit | Int64! | The maximum number of records to return in this request | 500 |
| totalCount | Int64! | The total number of available feed files matching the criteria | 1000 |
| hasMore | Boolean! | A boolean flag indicating if more pages are available (TRUE: next page exists; FALSE: last page reached) | TRUE |