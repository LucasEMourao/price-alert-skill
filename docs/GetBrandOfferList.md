-   [Open API Platform](https://affiliate.shopee.com.br/open_api/home)
-   [API List](https://affiliate.shopee.com.br/open_api/list)
-   [Open API Document](https://affiliate.shopee.com.br/open_api/document?type=overview)Must Read

Version 2.0

## Get Shop Offer List

Query: `shopOfferV2`

ResultType: `ShopOfferConnectionV2`

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
| shopId(New) | Int64 | Search by shop id | 84499012 |
| keyword | String | Search by shop name | demo |
| shopType(New) | \[Int\] | 

Filter by specific shop type  
OFFICIAL\_SHOP = 1;  
Filter mall shop  
PREFERRED\_SHOP = 2;  
Filter preferred(Star) shop  
PREFERRED\_PLUS\_SHOP = 4;  
Filter preferred(Star+) shop  


 | \[\],\[1,4\] |
| isKeySeller(New) | Bool | 

Filter for offers from Shopee's key sellers;  
TRUE = Offers from key sellers;  
FALSE = All offers regardless of the key seller status  


 | true |
| sortType | Int | 

SHOP\_LIST\_SORT\_TYPE\_LATEST\_DESC = 1;  
Sort by last update time

SHOP\_LIST\_SORT\_TYPE\_HIGHEST\_COMMISSION\_DESC = 2  
Sort by commission rate from high to low

SHOP\_LIST\_SORT\_TYPE\_POPULAR\_SHOP\_DESC = 3  
Sort by Popular shop from high to low



 |  |
| sellerCommCoveRatio(New) | String | 

The ratio of products with seller commission.  
e.g. set “0.123” if the rate is large or equal to 1.23%

 | "", “0.123” |
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
| nodes | \[ShopOfferV2\]! | Data list |  |
| pageInfo | PageInfo! | Page information |  |

ShopOfferV2 structure

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
| commissionRate | String | Commission rate, e.g. set “0.0123” if the rate is 1.23% | "0.25" |
| imageUrl | String | Image url | https://cf.shopee.co.id/file/id-11134201-7qul6-lfgbxyzg074186 |
| offerLink | String | Offer link | https://shope.ee/xxxxxxxx |
| originalLink | String | Original link | https://shopee.co.id/shop/19162748 |
| shopId | Int64 | Shop ID | 84499012 |
| shopName | String | Shop name | Ikea |
| ratingStar(New) | String | Shop Rating in Product Detail Page | "3.7" |
| shopType(New) | \[Int\] | 

OFFICIAL\_SHOP = 1;  
Product offers from official shops / Shopee Mall sellers  
PREFERRED\_SHOP = 2;  
Product offers from preferred sellers  
PREFERRED\_PLUS\_SHOP = 4;  
Product offers from preferred plus sellers  


 | \[\], \[1,4\] |
| remainingBudget(New) | Int | 

Remaining budget available for this seller's shop offer  
Unlimited (Offer does not have a budget limit. Offer will end only if the seller terminates the campaign) = 0  
Normal (Offer has above 50% budget remaining) = 3  
Low (Offer has below 50% budget remaining. Medium risk of running out of budget and offer being terminated early) = 2  
Very Low (Offer has below 30% budget remaining. High risk of running out of budget and offer being terminated early) = 1  


 | 1 |
| periodStartTime | Int | Offer start time | 1687712400 |
| periodEndTime | Int | Offer end time | 1690822799 |
| sellerCommCoveRatio(New) | String | The ratio of products with seller commission. e.g. set “0.0123” if the rate is large or equal to 1.23% | "", “0.123” |
| bannerInfo | BannerInfo | Banner Info |  |

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

BannerInfo structure

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
| count | Int | Banner quantity | 13 |
| banners | \[Banner!\]! | Banner |  |

Banner structure

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
| fileName | String | Image file name | "454.jpg" |
| imageUrl | String | Image url | https://cf.shopee.co.id/file/id-11134297-23010-kq42y2823wlv9d |
| imageSize | Int | Image size | 1747107 |
| imageWidth | Int | Image width | 5998 |
| imageHeight | Int | Image height | 3000 |

Error Code Description

| 
Error Code

 | 

Error Description

 | 

Remark

 |
| --- | --- | --- |
| 11000 | Business Error |  |
| 11001 | Params Error : {reason} |  |
| 11002 | Bind Account Error : {reason} |  |
| 10020 | Invalid Signature |  |
| 10020 | Your App has been disabled |  |
| 10020 | Request Expired |  |
| 10020 | Invalid Timestamp |  |
| 10020 | Invalid Credential |  |
| 10020 | Invalid Authorization Header |  |
| 10020 | Unsupported Auth Type |  |
| 10030 | Rate limit exceeded |  |
| 10031 | access deny |  |
| 10032 | invalid affiliate id |  |
| 10033 | account is frozen |  |
| 10034 | affiliate id in black list |  |
| 10035 | You currently do not have access to the Shopee Affiliate Open API Platform. Please contact us to request access or learn more. contact link : https://help.shopee.com.br/portal/webform/bbce78695c364ba18c9cbceb74ec9091 |  |