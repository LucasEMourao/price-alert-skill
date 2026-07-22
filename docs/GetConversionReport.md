-   [Open API Platform](https://affiliate.shopee.com.br/open_api/home)
-   [API List](https://affiliate.shopee.com.br/open_api/list)
-   [Open API Document](https://affiliate.shopee.com.br/open_api/document?type=overview)Must Read

## Get Conversion Report data

Query: `conversionReport`

ResultType: `ConversionReportConnection!`

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
| purchaseTimeStart | Int | Start of place order time range, unix timestamp |  |
| purchaseTimeEnd | Int | End of place order time range, unix timestamp |  |
| completeTimeStart | Int | Start of order complete time range, unix timestamp |  |
| completeTimeEnd | Int | End of place order time range, unix timestamp |  |
| shopName | String | Shop name |  |
| shopId | Int64 | Shop id |  |
| shopType | \[String\] | 

ShopType:  
ALL  
SHOPEE\_MALL\_CB  
SHOPEE\_MALL\_NON\_CB  
C2C\_CB  
C2C\_NON\_CB  
PREFERRED\_CB  
PREFERRED\_NON\_CB  


 | \[SHOPEE\_MALL\_CB\] |
| checkoutId(To Be Removed) | Int64 | Checkout id |  |
| conversionId | Int64 | ConversionId, known as Checkout id before |  |
| conversionStatus(To Be Removed) | String | Conversion Status:  
ALL(default),  
PENDING,  
COMPLETED,  
CANCELLED |  |
| orderId | String | Order id |  |
| productName | String | Product name |  |
| productId | Int64 | Product id |  |
| categoryLv1Id | Int64 | Level 1 category id |  |
| categoryLv2Id | Int64 | Level 2 category id |  |
| categoryLv3Id | Int64 | Level 3 category id |  |
| orderStatus | String | Order Status:  
ALL(default),  
UNPAID,  
PENDING,  
COMPLETED,  
CANCELLED |  |
| buyerType | String | Buyer type:  
ALL(default),  
NEW,  
EXISTING |  |
| attributionType | String | Attribution type:  
Ordered in Same Shop  
Ordered in Different Shop |  |
| device | String | Device type:  
ALL(default),  
APP,  
WEB |  |
| limit | Int | The maximum number of return data |  |
| fraudStatus | String | Fraud Status:  
ALL,  
UNVERIFIED,  
VERIFIED,  
FRAUD |  |
| scrollIdimportant | String | Page cursor, empty for the first query.  
Note: valid time is 30 seconds, that is, the time interval between two requests cannot exceed 30 seconds, Otherwise, the cursor expires, Need to re-initiate the query.  
If you need to query multiple pages of data, you need to Query Twice or more!  
The first query can get the content of the first page and scrollid, and the maximum number of data returned per page is 500  
Scrollid is used to help query the content of the second page and later. In order to get the content of the second page and later you Must Query with Scrollid  
Scrollid is one-time valid, the valid time is only 30 seconds  
So after the first request for scrollid, please query the content of the second and later page within 30 seconds  
The query without scrollid requires an interval of longer than 30 seconds |  |
| campaignPartnerName(New) | String | Affiliate campaign partner |  |
| campaignType(New) | String | Campaign Type:  
ALL(default),  
Seller Open Campaign,  
Seller Target Campaign,  
MCN Campaign,  
Non-Seller Campaign |  |

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
| nodes | \[ConversionReport\]! | Data list |  |
| pageInfo | PageInfo! | Page information |  |

ConversionReport structure

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
| purchaseTime | Int | 

Purchase Time

 |  |
| clickTime | Int | Click Link Time |  |
| checkoutId(To Be Removed) | Int64 | Conversion id |  |
| conversionId | Int64 | Conversion id |  |
| conversionStatus(To Be Removed) | String | 

Conversion Status:  
ALL  
PENDING  
COMPLETED  
CANCELLED

 |  |
| grossCommission(To Be Removed) | String | Gross Shopee Commission  
Calculated Shopee commission before commission cap applies  
Note: The unit is the local currency |  |
| cappedCommission(To Be Removed) | String | Capped Shopee Commission  
Calculated Shopee commission after commission cap applies  
Note: The unit is the local currency |  |
| totalBrandCommission(To Be Removed) | String | Total seller commission in one conversion.  
Note: The unit is the local currency |  |
| estimatedTotalCommission(To Be Removed) | String | Gross Commission  
Estimated total commission will be paid to you (before validation) |  |
| shopeeCommissionCapped | String | Gross Shopee Commission: Calculated Shopee commission after commission cap applies.  
Note: Amounts are denoted in local currency. |  |
| sellerCommission | String | Gross Seller Commission: Calculated Seller commission.  
Note: Amounts are denoted in local currency. |  |
| totalCommission | String | Gross commission from the seller and Shopee, after applying the commission cap but before deducting the MCN management fee.  
Note: Amounts are denoted in local currency. |  |
| buyerType | String | Buyer Status  
Buyer status: New or Existing |  |
| utmContent | String | sub id  
Value(s) passed in your sub-id(s) parameter in your Affiliate link(s) |  |
| device | String | Device type |  |
| referrer | String | Referrer |  |
| orders | \[ConversionReportOrder\]! | Order list in conversion |  |
| linkedMcnName(New) | String | The name of MCN that affiliate has been linked with. |  |
| mcnContractId(New) | Int64 | The contract id between affiliate and linked MCN |  |
| mcnManagementFeeRate(New) | String | The rate of the management fee allocated to the MCN, based on the gross commission. |  |
| mcnManagementFee(New) | String | The management fee allocated to MCN based on total gross commission.  
Note: Amounts are denoted in local currency. |  |
| netCommission(New) | String | Net commission from the seller and Shopee, calculated after applying the commission cap and deducting the MCN management fee.  
Note: Amounts are denoted in local currency. |  |
| campaignType(New) | String | Campaign Type:  
ALL(default),  
Seller Open Campaign,  
Seller Target Campaign,  
MCN Campaign,  
Non-Seller Campaign |  |

ConversionReportOrder structure

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
| orderId | String | Order id |  |
| orderStatus | String | Order Status:  
UNPAID,  
PENDING,  
COMPLETED,  
CANCELLED |  |
| shopType | String | 

Shop type:  
SHOPEE\_MALL\_CB  
SHOPEE\_MALL\_NON\_CB  
C2C\_CB  
C2C\_NON\_CB  
PREFERRED\_CB  
PREFERRED\_NON\_CB  


 |  |
| items | \[ConversionReportOrderItem\]! | Item list in order |  |

ConversionReportOrderItem structure

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
| shopId | Int64 | Shop id |  |
| shopName | String | Shop name |  |
| completeTime | Int | open\_api\_order\_completed\_time\_description |  |
| itemId | Int64 | Item id |  |
| itemName | String | Item name |  |
| itemPrice | String | Item price  
Note: The unit is the local currency |  |
| displayItemStatus(New) | String | The combined status of order status and fraud status for item |  |
| actualAmount | String | Purchase Value:  
Paid item value of user when purchase. Excluded from rebates (vouchers, discounts, cashback, etc) and shipping fee.  
Note: Amounts are denoted in local currency. |  |
| qty | Int | Item Quantity |  |
| imageUrl | String | Image url |  |
| itemCommission(To Be Removed) | String | Item Shopee Commission  
Total Shopee platform commission in one item(before checkout cap)  
Note: The unit is the local currency |  |
| grossBrandCommission(To Be Removed) | String | Item Brand Commission  
Additional commission from Brand offers in one item. Will be added on top of Shopee commission  
Note: The unit is the local currency |  |
| itemTotalCommission | String | Total commission from seller and Shopee before MCN management fee deduction.  
Note: Amounts are denoted in local currency. |  |
| itemSellerCommission | String | Commission from Seller offers in one item.  
Note: Amounts are denoted in local currency. |  |
| itemSellerCommissionRate | String | The rate of the commission offered by the seller |  |
| itemShopeeCommissionCapped | String | Shopee platform commission in one item(after order cap).  
Note: Amounts are denoted in local currency. |  |
| itemShopeeCommissionRate | String | The rate of the commission offered by Shopee |  |
| itemNotes | String | Textual explanation of pending, cancel, and fraud status |  |
| channelType | String | Buyer order source channels |  |
| attributionType | String | Buyer order specific type |  |
| globalCategoryLv1Name | String | 

Level 1 global category name

 |  |
| globalCategoryLv2Name | String | Level 2 global category name |  |
| globalCategoryLv3Name | String | Level 3 global category name |  |
| fraudStatus | String | Fraud status |  |
| modelId | Int64 | Model id is the unique id per item variation |  |
| promotionId | String | Promotion id is the unique id per bundle deal and add on deal items |  |
| campaignPartnerName(New) | String | The name of the campaign partner who initiated the MCN campaign that affiliate promoted and drove orders for. |  |
| campaignType(New) | String | Campaign Type:  
ALL(default),  
Seller Open Campaign,  
Seller Target Campaign,  
MCN Campaign,  
Non-Seller Campaign |  |

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
| limit | Int | Number of data per page | 20 |
| hasNextPage | Bool | If it has next page | true |
| scrollId | String | Page cursor, empty for the first query.  
Note: valid time is 30 seconds, that is, the time interval between two requests cannot exceed 30 seconds, Otherwise, the cursor expires, Need to re-initiate the query.  
If you need to query multiple pages of data, you need to Query Twice or more!  
The first query can get the content of the first page and scrollid, and the maximum number of data returned per page is 500  
Scrollid is used to help query the content of the second page and later. In order to get the content of the second page and later you Must Query with Scrollid  
Scrollid is one-time valid, the valid time is only 30 seconds  
So after the first request for scrollid, please query the content of the second and later page within 30 seconds  
The query without scrollid requires an interval of longer than 30 seconds |  |

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