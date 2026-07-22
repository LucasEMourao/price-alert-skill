-   [Open API Platform](https://affiliate.shopee.com.br/open_api/home)
-   [API List](https://affiliate.shopee.com.br/open_api/list)
-   [Open API Document](https://affiliate.shopee.com.br/open_api/document?type=overview)Must Read

## Get Product Feed Offer List

Query: `listItemFeeds`

ResultType: `ItemFeedListConnection!`

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
| feedMode | FeedMode | 

Optional  
1\. 'FULL' (Default): Contains every product in that category. Use this for your first download.  
2\. 'DELTA': Only contains products that were added, updated, or removed since yesterday.

 | FULL |

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
| feeds | \[ItemFeed!\]! | Offer Data List |  |

ItemFeed structure

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
| datafeedId | String! | The unique key used to fetch specific file details for the product catalog. | 12345\_FULL\_20260205 |
| datafeedName | String! | The display name of the product catalog | Home Appliance - Preferred |
| referenceId | String! | An identifier that enables clients to map delta updates to the corresponding full feed | 373421936506056704 |
| description | String! | A brief summary of the catalog content |  |
| totalCount | Int64! | Total number of products within the catalog | 509 |
| date | String! | The date when the product catalog was last synchronized or updated | 2026-02-08 |
| feedMode | FeedMode! | 

1\. 'FULL' (Default): Contains every product in that category. Use this for your first download.  
2\. 'DELTA': Only contains products that were added, updated, or removed since yesterday.

 | FULL |