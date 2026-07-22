-   [Open API Platform](https://affiliate.shopee.com.br/open_api/home)
-   [API List](https://affiliate.shopee.com.br/open_api/list)
-   [Open API Document](https://affiliate.shopee.com.br/open_api/document?type=overview)Must Read

Version 2.0

## Get Shopee Offer List

Query: `shopeeOfferV2`

ResultType: `ShopeeOfferConnectionV2!`

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
| keyword | String | Search by offer name | clothes |
| sortType | Int | 

LATEST\_DESC = 1  
Sort offers by latest update time

HIGHEST\_COMMISSION\_DESC = 2  
Sort offers by commission rate from high to low



 | 1 |
| page | Int | Page number | 2 |
| limit | Int | Number of data per page | 10 |

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
| nodes | \[ShopeeOfferV2\]! | Data list |  |
| pageInfo | PageInfo! | Page information |  |

ShopeeOfferV2 structure

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
| commissionRate | String | Commission rate, e.g. set “0.0123” if the rate is 1.23% |  |
| imageUrl | String | Image url |  |
| offerLink | String | Offer link |  |
| originalLink | String | Original link |  |
| offerName | String | Offer name |  |
| offerType | Int | 

CAMPAIGN\_TYPE\_COLLECTION = 1;  
CAMPAIGN\_TYPE\_CATEGORY = 2;

 |  |
| categoryId | Int64 | 

CategoryId returns when  
offerType = CAMPAIGN\_TYPE\_CATEGORY

 |  |
| collectionId | Int64 | 

CollectionId returns when  
offerType = CAMPAIGN\_TYPE\_COLLECTION

 |  |
| periodStartTime | Int | Offer start time |  |
| periodEndTime | Int | Offer end time |  |

PageInfo structure

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
| page | Int | The current page number | 2 |
| limit | Int | Number of data per page | 10 |
| hasNextPage | Bool | If it has next page | true |