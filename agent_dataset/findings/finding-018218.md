---
id: 18218
severity: "High"
---

# A temporary issue shows in the staking functionality which leads to the users receiving less minted tokens

## Description

A quick explanation of the issue causing it, the problem is based on the function “ethPerDerivative” in the Reth derivative.

As you can see two statements can be triggered here, the first one “if (poolCanDeposit(_amount))” checks if the given amount + the pool balance isn’t greater than the maximumDepositPoolSize and that the amount is greater than the minimum deposit in the pool. Second statement is meant to return a poolPrice which is slightly more than the regular one, because it’s used in order to swap tokens in Uniswap and therefore the price per token is overpriced.

```solidity
function ethPerDerivative(uint256 _amount) public view returns (uint256) {
    if (poolCanDeposit(_amount))
        return RocketTokenRETHInterface(rethAddress()).getEthValue(10 ** 18);
    else return (poolPrice() * 10 ** 18) / (10 ** 18);
}
```

// poolCanDeposit() returns:
return rocketDepositPool.getBalance() + _amount <= rocketDAOProtocolSettingsDeposit.getMaximumDepositPoolSize() && _amount >= rocketDAOProtocolSettingsDeposit.getMinimumDeposit();

Below you can see the regular price returned in the first statement - 1063960369075232250:

![Screenshot 2023-03-27 at 8 53 34](https://user-images.githubusercontent.com/112419701/227852484-9bf0144d-820d-414c-8cb9-e1fb44f5c806.png)

Below you can see the pool price from the second statement, supposed to be used only when a swap is made.

```solidity
else return (poolPrice() * 10 ** 18) / (10 ** 18);
```

// poolPrice calculates and returns
```solidity
uint160 sqrtPriceX96, , , , , , ) = pool.slot0();
return (sqrtPriceX96 * (uint(sqrtPriceX96)) * (1e18)) >> (96 * 2);
```

// uint160 sqrtPriceX96 = 81935751724326368909606241317
// return (sqrtPriceX96 * (uint(sqrtPriceX96)) * (1e18)) >> (96 * 2);
// return 1069517062752670179 (pool price)

// The function "ethPerDerivative" for the else statement return (poolPrice() * 10 ** 18) / (10 ** 18);
// Which will be - 1069517062752670179

Difference between the regular price and the pool price:

regular price - 1063960369075232250  
pool price - 1069517062752670179

## Proof of Concept

Will start from the start in order to get the right amounts of “totalSupply” and the Reth balance of derivative. So I can show the issue result in POC Part 2.

The values below are only made for the example.

Let’s say we have two stakers - Bob and Kiki each depositing 100e18.

We have only one derivative which is Reth, so it will have 100% weight.

Bob deposits 100e18 as the first depositer and receives (99999999999999999932) minted tokens of safETH.

So far after Bob deposit:

totalSupply = 99999999999999999932  
Reth derivative balance = 93988463204618701706

```solidity
uint256 underlyingValue = 0;
uint256 totalSupply = 0; 
uint256 preDepositPrice = 1e18

// As we have only derivative Reth in the example, it owns all of the weight.
uint256 ethAmount = (msg.value * weight) / totalWeight;
uint256 ethAmount = (100e18 * 1000) / 1000;

// not applying the deposit fee in rocketPool

uint256 depositAmount = derivative.deposit{value: ethAmount}();
uint256 depositAmount = 93988463204618701706

uint derivativeReceivedEthValue = (derivative.ethPerDerivative(depositAmount) * depositAmount) / 10 ** 18;
uint derivativeReceivedEthValue = (1063960369075232250 * 93988463204618701706) / 10 ** 18;
uint derivativeReceivedEthValue = 99999999999999999932

totalStakeValueEth = 99999999999999999932;

uint256 mintAmount = (totalStakeValueEth * 10 ** 18) / preDepositPrice;
uint256 mintAmount = (99999999999999999932 * 10 ** 18) / 1e18;
uint256 mintAmount = 99999999999999999932
```

Kiki deposits 100e18 as well and receives (99999999999999999932) minted tokens of safEth.

So far after Kiki’s deposit:

totalSupply = 199999999999999999864;  
Reth derivative balance = 187976926409237403412;

```solidity
// take the info after bob's deposit and the normal price
underlyingValue  = (derivatives[i].ethPerDerivative(derivatives[i].balance()) * derivatives[i].balance()) / 10 ** 18;
uint256 underlyingValue = (1063960369075232250 * 93988463204618701706) / 10 ** 18;
uint256 underlyingValue = 99999999999999999932;

uint256 totalSupply = 99999999999999999932; 

uint256 preDepositPrice = (10 ** 18 * underlyingValue) / totalSupply;
uint256 preDepositPrice = (10 ** 18 * 99999999999999999932) / 99999999999999999932;
uint256 preDepositPrice = 1e18;

// As we have only derivative Reth in the example, it owns all of the weight.
uint256 ethAmount = (msg.value * weight) / totalWeight;
uint256 ethAmount = (100e18 * 1000) / 1000;

// not applying the deposit fee in rocketPool
uint256 depositAmount = 93988463204618701706

uint derivativeReceivedEthValue = (derivative.ethPerDerivative(depositAmount) * depositAmount) / 10 ** 18;
uint derivativeReceivedEthValue = (1063960369075232250 * 93988463204618701706) / 10 ** 18;
uint derivativeReceivedEthValue = 99999999999999999932

totalStakeValueEth = 99999999999999999932;
 
uint256 mintAmount = (totalStakeValueEth * 10 ** 18) / preDepositPrice;
uint256 mintAmount = (99999999999999999932 * 10 ** 18) / 1e18;
uint256 mintAmount = 99999999999999999932
```

From the first POC, we calculated the outcome of 200e18 staked into the Reth derivative. We got the totalSupply and the Reth balance the derivative holds. So we can move onto the main POC, where I can show the difference and how much less minted tokens the user gets.

```solidity
totalSupply = 199999999999999999864;
Reth derivative balance = 187976926409237403412;
```

First I am going to show how much minted tokens the user is supposed to get without applying the issue occurring. And after that I will do the second one and apply the issue. So we can compare the outcomes and see how much less minted tokens the user gets.

Without the issue occurring, a user deposits 5e18 by calling the staking function. The user received (4999549277935239332) minted tokens of safEth.

```solidity
uint256 underlyingValue  = (derivatives[i].ethPerDerivative(derivatives[i].balance()) * derivatives[i].balance()) / 10 ** 18;
uint256 underlyingValue  = (1063960369075232250 * 187976926409237403412) / 10 ** 18;
uint256 underlyingValue  = 199999999999999999864;

uint256 totalSupply = 199999999999999999864; 

uint256 preDepositPrice = (10 ** 18 * underlyingValue) / totalSupply;
uint256 preDepositPrice = (10 ** 18 * 199999999999999999864) / 199999999999999999864;
uint256 preDepositPrice = 1e18;

// As we have only derivative Reth in the example, it owns all of the weight.
uint256 ethAmount = (msg.value * weight) / totalWeight;
uint256 ethAmount = (5e18 * 1000) / 1000;

// not applying the deposit fee in rocketPool
uint256 depositAmount = 4698999533488942411

uint derivativeReceivedEthValue = (derivative.ethPerDerivative(depositAmount) * depositAmount) / 10 ** 18;
uint derivativeReceivedEthValue = (1063960369075232250 * 4698999533488942411) / 10 ** 18;
uint derivativeReceivedEthValue = 4999549277935239332

totalStakeValueEth = 4999549277935239332;
 
uint256 mintAmount = (totalStakeValueEth * 10 ** 18) / preDepositPrice;
uint256 mintAmount = (4999549277935239332 * 10 ** 18) / 1e18;
uint256 mintAmount = 4999549277935239332
```

Stats after the deposit without the issue:

```solidity
totalSupply = 204999549277935239196
Reth derivative balance = 192675925942726345823;
```

This time we apply the issue occurring and as the first one a user deposits 5e18 by calling the staking function. The user receives (4973574036557377784) minted tokens of saEth

```solidity
uint256 underlyingValue  = (derivatives[i].ethPerDerivative(derivatives[i].balance()) * derivatives[i].balance()) / 10 ** 18;
// the function takes as account the pool price here which is overpriced.
uint256 underlyingValue  = (1069517062752670179 * 187976926409237403412) / 10 ** 18;
uint256 underlyingValue  = 201044530198482424206

uint256 totalSupply = 199999999999999999864;

uint256 preDepositPrice = (10 ** 18 * underlyingValue) / totalSupply;
uint256 preDepositPrice = (10 ** 18 * 201044530198482424206) / 199999999999999999864;
uint256 preDepositPrice = 1005222650992412121;

// As we have only derivative Reth in the example, it owns all of the weight.
uint256 ethAmount = (msg.value * weight) / totalWeight;
uint256 ethAmount = (5e18 * 1000) / 1000;

// not applying the deposit fee in rocketPool
uint256 depositAmount = 4698999533488942411

// Here the function calculates based on the normal price, as the pool has free space and the user deposits only 5e18.
uint derivativeReceivedEthValue = (derivative.ethPerDerivative(depositAmount) * depositAmount) / 10 ** 18;
uint derivativeReceivedEthValue = (1063960369075232250 * 4698999533488942411) / 10 ** 18;
uint derivativeReceivedEthValue = 4999549277935239332

totalStakeValueEth = 4999549277935239332;
 
uint256 mintAmount = (totalStakeValueEth * 10 ** 18) / preDepositPrice;
uint256 mintAmount = (4999549277935239332 * 10 ** 18) / 1005222650992412121;
uint256 mintAmount = 4973574036557377784
```

Stats after the deposit with the issue:

```solidity
totalSupply = 204973574036557377648;
Reth derivative balance = 192675925942726345823;
```

Difference between outcomes:

Without the issue based on 5e18 deposit, the user receives - 4999549277935239332 minted tokens  
With the issue occurring based on 5e18 deposit, the user receives - 4973574036557377784 minted tokens

So far we found that this issue leads to users receiving less minted shares, but let’s go even further and see how much the user losses in terms of ETH. By unstaking the minted amount.

First we apply the stats without the issue occurring.

```solidity
totalSupply = 204999549277935239196
Reth derivative balance = 192675925942726345823;

uint256 derivativeAmount = (derivatives[i].balance() * _safEthAmount) / safEthTotalSupply;
uint256 derivativeAmount = (192675925942726345823 * 4999549277935239332) / 204999549277935239196;
uint256 derivativeAmount = 4698999533488942410;

// Eth value based on the current eth price
// Reth to Eth value - 4698999533488942410 => 4.999999999999999998 - 8766.85 usd
```

Second we apply the stats with the issue occurring.

```solidity
totalSupply = 204973574036557377648;
Reth derivative balance = 192675925942726345823;

uint256 derivativeAmount = (derivatives[i].balance() * _safEthAmount) / safEthTotalSupply;
uint256 derivativeAmount = (192675925942726345823 * 4973574036557377784) / 204973574036557377648;
uint256 derivativeAmount = 4675178189396666336;

// Eth value based on the current eth price
// Reth to Eth value - 4675178189396666336 => 4.974637740558436705 - 8722.41 usd
```

## Recommendation

The problem occurs with calculating the underlyingValue in the staking function. The function “ethPerDerivative” is called with all of the Reth balance, which should not be the case here. Therefore the function calls “poolCanDeposit” in order to check if the pool has space for the Reth derivative balance (Basically the contract thinks that the Reth balance in the derivative will be deposited in the pool, which is not the case here). So even if the pool has space for the depositing amount by the user, the poolCanDeposit(_amount) will return false and the contract will get the poolPrice of the reth which is supposed to be used only for the swap in Uniswap. The contract process executing the staking function with the overpriced pool price and doesn’t perform any swap, but deposits the user funds to the pool.

```solidity
underlyingValue += (derivatives[i].ethPerDerivative(derivatives[i].balance()) * derivatives[i].balance()) / 10 ** 18;
```

```solidity
function ethPerDerivative(uint256 _amount) public view returns (uint256) {
    if (poolCanDeposit(_amount))
        return RocketTokenRETHInterface(rethAddress()).getEthValue(10 ** 18);
    else return (poolPrice() * 10 ** 18) / (10 ** 18);
}
```

return rocketDepositPool.getBalance() + _amount <= rocketDAOProtocolSettingsDeposit.getMaximumDepositPoolSize() && _amount >= rocketDAOProtocolSettingsDeposit.getMinimumDeposit();

I’d recommend creating a new function in the reth derivative contract. Which converts the msg.value to reth tokens and using it instead of the whole Reth balance the derivative holds.

```solidity
function rethValue(uint256 _amount) public view returns (uint256) {
    RocketTokenRETHInterface(rethAddress()).getRethValue(amount);
}
```

Like this we check if the msg.value converted into reth tokens is below the maximumPoolDepositSize and greater than the minimum deposit.

```solidity
underlyingValue += (derivatives[i].ethPerDerivative(derivatives[i].rethValue(msg.value)) * derivatives[i].balance()) / 10 ** 18;
```

This report is great but only tackles a part of the problem: the pricing method is versatile and manipulable, so it can 1 - lead to a loss of funds as show here depending on the condition but more importantly be manipulated easily.

Don’t get rETH from pool on deposits.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an asymmetric pricing bug in the staking workflow of a protocol that uses a rETH derivative. The contract calls the function ethPerDerivative to obtain the ETH value of a derivative balance, but the function decides which price to return based on the result of poolCanDeposit. When the total rETH balance held by the derivative plus the queried amount exceeds the maximum pool deposit size, poolCanDeposit returns false and ethPerDerivative falls back to returning poolPrice, a value that is deliberately inflated for use in Uniswap swaps. Because the staking logic passes the entire derivative balance to ethPerDerivative instead of the user‑specific deposit amount, the fallback branch is triggered after the pool becomes partially filled. Consequently the protocol values the user’s stake with the overpriced pool price even though no swap is performed, which reduces the amount of minted share tokens (safETH) the user receives. The impact is that stakers receive fewer minted tokens than they expect, effectively losing ETH value; the discrepancy can be observed as a lower token balance or a reduced share price after a deposit. The bug manifests only when the pool is close to its deposit limit, making it hard to notice because the price difference is small and the UI simply shows a smaller mint amount without explaining why. It affects any user who stakes after the pool reaches the threshold, as well as the protocol’s accounting and token economics. The issue was discovered during a formal audit by reproducing the staking calculations and observing that the underlying value used for minting diverged from the regular rETH‑to‑ETH conversion. The root cause is the misuse of a pricing function that was intended solely for swap operations and the inappropriate use of poolCanDeposit as a guard for valuation, leading to a logical flaw in the valuation path. To remediate, the contract should separate the valuation of a user’s deposit from the swap price calculation, for example by introducing a dedicated function that converts the deposited ETH amount to rETH value using the standard getEthValue call, and by ensuring ethPerDerivative is only used with amounts that pass the poolCanDeposit check or by removing the poolCanDeposit condition from the valuation altogether. This eliminates the reliance on the inflated pool price for stake valuation, restores correct minting ratios, and prevents users from receiving fewer tokens than warranted.
