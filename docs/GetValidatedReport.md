-   [Open API Platform](https://affiliate.shopee.com.br/open_api/home)
-   [API List](https://affiliate.shopee.com.br/open_api/list)
-   [Open API Document](https://affiliate.shopee.com.br/open_api/document?type=overview)Must Read

## Get Validated Report Data

Query: `validatedReport`

ResultType: `ValidatedReportConnection!`

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
| validationId(New) | Int64 | Validation id, can be found in Billing Information |  |
| limit | Int | The maximum number of return data |  |
| scrollIdimportant | String | 

Page cursor, empty for the first query.  
Note: valid time is 30 seconds, that is, the time interval between two requests cannot exceed 30 seconds, Otherwise, the cursor expires, Need to re-initiate the query.If you need to query multiple pages of data, you need to Query Twice or more!  
The first query can get the content of the first page and scrollid, and the maximum number of data returned per page is 500  
Scrollid is used to help query the content of the second page and later. In order to get the content of the second page and later you Must Query with Scrollid  
Scrollid is one-time valid, the valid time is only 30 seconds  
So after the first request for scrollid, please query the content of the second and later page within 30 seconds  
The query without scrollid requires an interval of longer than 30 seconds  


 |  |

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
| nodes | \[ValidatedReport\]! | Data list |  |
| pageInfo | PageInfo! | Page information |  |

ValidatedReport structure

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
| purchaseTime | Int | Purchase Time |  |
| clickTime | Int | Click Link Time |  |
| conversionId | Int64 | Conversion id |  |
| shopeeCommissionCapped | String | 

Gross Shopee Commission: Calculated Shopee commission after commission cap applies.  
Note: Amounts are denoted in local currency.  


 |  |
| sellerCommission | String | 

Gross Seller Commission: Calculated Seller commission.  
Note: Amounts are denoted in local currency.  


 |  |
| totalCommission | String | 

Gross Commission from Shopee and Seller after commission cap applies.  
Note: Amounts are denoted in local currency.  


 |  |
| buyerType | String | 

Buyer Status  
Buyer status: New or Existing  


 |  |
| utmContent | String | 

Sub id  
Value(s) passed in your sub-id(s) parameter in your Affiliate link(s)  


 |  |
| device | String | Device type |  |
| referrer | String | Referrer |  |
| orders | \[ValidatedReportOrder\]! | Order list in conversion |  |
| linkedMcnName(New) | String | The name of MCN that affiliate has been linked with. |  |
| mcnContractId(New) | String | The contract id between affiliate and linked MCN |  |
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

ValidatedReportOrder structure

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
| orderStatus | String | 

Order Status  
UNPAID  
PENDING  
COMPLETED  
CANCELLED  


 |  |
| shopType | String | 

Shop type:  
SHOPEE\_MALL\_CB  
SHOPEE\_MALL\_NON\_CB  
C2C\_CB  
C2C\_NON\_CB  
PREFERRED\_CB  
PREFERRED\_NON\_CB  


 |  |
| items | \[ValidatedReportOrderItem\]! | Item list in order |  |

ValidatedReportOrderItem structure

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
| completeTime | Int | Affiliate Order Complete Time |  |
| itemId | Int64 | Item id |  |
| itemName | String | Item name |  |
| itemPrice | String | 

Item price  
Note: The unit is the local currency  


 |  |
| displayItemStatus(New) | String | The combined status of order status and fraud status for item |  |
| actualAmount | String | 

Purchase Value:  
Paid item value of user when purchase. Excluded from rebates (vouchers, discounts, cashback, etc) and shipping fee.  
Note: Amounts are denoted in local currency.  


 |  |
| qty | Int | 

Item Quantity.  
Note: It refers to adjusted item quantity for the Adjusted Orders.

 |  |
| imageUrl | String | Image url |  |
| itemTotalCommission | String | 

Total commission from seller and Shopee.  
Note: Amounts are denoted in local currency.

 |  |
| itemSellerCommission | String | 

Commission from Seller offers in one item.  
Note: Amounts are denoted in local currency.

 |  |
| itemSellerCommissionRate | String | The rate of the commission offered by the seller |  |
| itemShopeeCommissionCapped | String | 

Shopee platform commission in one item(after order cap).  
Note: Amounts are denoted in local currency.

 |  |
| itemShopeeCommissionRate | String | The rate of the commission offered by Shopee |  |
| itemNotes | String | Textual explanation of pending, cancel, and fraud status |  |
| channelType | String | Buyer order source channels |  |
| attributionType | String | Buyer order specific type |  |
| globalCategoryLv1Name | String | Level 1 global category name |  |
| globalCategoryLv2Name | String | Level 2 global category name |  |
| globalCategoryLv3Name | String | Level 3 global category name |  |
| refundAmount | String | 

Refund amount  
Only for Digital Product, order confirmed received by user with partial refund  


 |  |
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
| scrollId | String | 

Page cursor, empty for the first query.  
Note: valid time is 30 seconds, that is, the time interval between two requests cannot exceed 30 seconds, Otherwise, the cursor expires, Need to re-initiate the query.  
If you need to query multiple pages of data, you need to Query Twice or more!  
The first query can get the content of the first page and scrollid, and the maximum number of data returned per page is 500  
Scrollid is used to help query the content of the second page and later. In order to get the content of the second page and later you Must Query with Scrollid  
Scrollid is one-time valid, the valid time is only 30 seconds  
So after the first request for scrollid, please query the content of the second and later page within 30 seconds  
The query without scrollid requires an interval of longer than 30 seconds  


 |  |

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