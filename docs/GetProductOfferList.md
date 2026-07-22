itemIdInt64Item ID17979995178commissionRateStringMaximum Commission rate, e.g. set “0.0123” if the rate is 1.23%"0.25"sellerCommissionRate(New)StringSeller Commission rate (Commission Xtra rate)"0.25"shopeeCommissionRate(New)StringShopee Commission rate"0.25"commission(New)String

Commission amount = price \* commissionRate  
Note: The unit is the local currency  

"27000"appExistRate(To Be Removed)StringCommission rate for non-first-time order users of this product on the app, e.g. set “0.0123” if the rate is 1.23%appNewRate(To Be Removed)StringCommission rate for new users of this product on the app, e.g. set “0.0123” if the rate is 1.23%webExistRate(To Be Removed)StringCommission rate for non-first-time order users on the web, e.g. set “0.0123” if the rate is 1.23%webNewRate(To Be Removed)StringCommission rate for new users of this product on the web, e.g. set “0.0123” if the rate is 1.23%price(To Be Removed)StringProduct Price  
Note: The unit is the local currencysalesInt32Sales count for this product25priceMax(New)String

Product maximum price  
Note: The unit is the local currency  

"55.99"priceMin(New)String

Product minimum price  
Note: The unit is the local currency  

"45.99"productCatIds(New)\[Int\]Product category id. Returns category id level 1, level 2, level 3 in order, or 0 if the relevant level does not exist.\[100012,100068,100259\]ratingStar(New)StringThe product rating shown in Shopee Product Page"4.7"priceDiscountRate(New)IntThe price discount shown in Shopee Product Page. 10 represents 10%10imageUrlStringImage urlproductNameStringProduct nameIKEA starfishshopId(New)Int64Shop id84499012shopNameStringShop nameIKEAshopType(New)\[Int\]

OFFICIAL\_SHOP = 1;  
Product offers from official shops / Shopee Mall sellers  
PREFERRED\_SHOP = 2;  
Product offers from preferred sellers  
PREFERRED\_PLUS\_SHOP = 4;  
Product offers from preferred plus sellers  

\[\], \[1,4\]productLinkStringProduct linkhttps://shopee.co.id/product/14318452/4058376611offerLinkStringOffer linkhttps://shope.ee/xxxxxxxxperiodStartTimeIntOffer Start Time1687539600periodEndTimeIntOffer End Time1688144399