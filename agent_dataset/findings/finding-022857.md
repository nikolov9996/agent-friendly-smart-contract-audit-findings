---
id: 22857
severity: "High"
---

# redeem stake token may be Dos because there

## Description

```solidity
function createMintStakeTokenRequest(MintStakeTokenParams calldata params)
external payable override nonReentrant {
    ...
    if (params.walletRequestTokenAmount > 0) {
        require(!params.isNativeToken || msg.value ==
        params.walletRequestTokenAmount, "Deposit eth amount error!");
        AssetsProcess.depositToVault(
            AssetsProcess.DepositParams(
                account,
                params.requestToken,
                params.walletRequestTokenAmount,
                params.isCollateral ? AssetsProcess.DepositFrom.MINT_COLLATERAL
                : AssetsProcess.DepositFrom.MINT,
                params.isNativeToken
            )
        );
    }
```
```solidity
function depositToVault(DepositParams calldata params) public returns (address) {
    IVault vault = IVault(address(this));
    address targetAddress;
    // get related vault
    if (DepositFrom.MANUAL == params.from || DepositFrom.MINT_COLLATERAL ==
    params.from) {
        targetAddress = vault.getPortfolioVaultAddress();
    } else if (DepositFrom.ORDER == params.from) {
        targetAddress = vault.getTradeVaultAddress();
    } else if (DepositFrom.MINT == params.from) {
        targetAddress = vault.getLpVaultAddress();
    }
```
Funds will be transferred to portfolio vault if the staker stake via MINT_COLLATERAL, and be transferred to stake LP Pool if the staker stake via MINT. When LP holders redeem tokens, all tokens will come from LP Pool. This can lead to redeem reverted because there is not enough balance.
When liquidity providers want to stake liquidity, liquidity providers can stake via MINT_COLLATERAL or MINT. The liquidity will be transferred to different vault, depending on mint method. Liquidity will be transferred to portfolio vault when isCollateral = true, otherwise will be transferred to stake LP Pool at last.
The vulnerability is that when LP holders try to redeem tokens, all redeem tokens will come from LP Vault. This could lead to redeem reverted because there may not be enough balance.
The hacker can deposit via isCollateral = true to transfer tokens to portfolio vault and increase LP pool's share amount. And then the hacker can redeem tokens from LP pool. This will cause other normal LP holders cannot redeem tokens. Even if there is no hacker, the system may meet this case in normal scenairo.
LP holders can not redeem tokens.

## Proof of Concept

Add this test case into mintStakeToken.test.ts, user0 stake with isCollateral = true, and then user1 stakes with isCollateral = false. Then user1 redeems tokens, and after that, user0 cannot redeem his tokens.
```solidity
it.only('Case3.1: Stake with mint_collateral', async function () {
    const stakeToken = await ethers.getContractAt('StakeToken', xEth)
    const preWEthTokenBalance = BigInt(await weth.balanceOf(user0.address))
    const preEthTokenBalance = BigInt(await ethers.provider.getBalance(user0.address))
    const preWEthVaultBalance = BigInt(await weth.balanceOf(lpVaultAddr))
    const preEthVaultBalance = BigInt(await ethers.provider.getBalance(wethAddr))
    const preWEthMarketBalance = BigInt(await weth.balanceOf(xEth))
    const preStakeTokenBalance = BigInt(await stakeToken.balanceOf(user0.address))
    const tokenPrice = precision.price(1800)
    const oracle = [{ token: wethAddr, minPrice: tokenPrice, maxPrice: tokenPrice }]
    const executionFee = precision.token(2, 15)
    // user0 mint
    await handleMint(fixture, {
        requestToken: weth,
        requestTokenAmount: precision.token(300),
        oracle: oracle,
        account: user0,
        isNativeToken: false,
        isCollateral: true,
        executionFee: executionFee,
    })
    //console.log(weth.balanceOf(stakeToken))
    let stakeWethBalance = BigInt(await weth.balanceOf(stakeToken))
    let portfolioVaultWethBalance = BigInt(await weth.balanceOf(portfolioVaultAddr))
    console.log(stakeWethBalance)
    console.log(portfolioVaultWethBalance)
    // user1 mint
    await handleMint(fixture, {
        requestToken: weth,
        requestTokenAmount: precision.token(300),
        oracle: oracle,
        account: user1,
        isNativeToken: false,
        isCollateral: false,
        executionFee: executionFee,
    })
    stakeWethBalance = BigInt(await weth.balanceOf(stakeToken))
    // Dump information
    console.log(stakeWethBalance)
    console.log(portfolioVaultWethBalance)
    // user1 redeem
    const tokenPrice1 = precision.price(1800)
    console.log(BigInt(await stakeToken.balanceOf(user0))) // 299.xxx, fees
    console.log(BigInt(await stakeToken.balanceOf(user1)))
    await handleRedeem(fixture, {
        unStakeAmount: precision.token(299),
        account: user1,
        receiver: user1.address,
        oracle: [{ token: wethAddr, minPrice: tokenPrice1, maxPrice: tokenPrice1 }],
    })
    console.log()
    // user0 cannot redeem
    stakeWethBalance = BigInt(await weth.balanceOf(stakeToken))
    console.log(BigInt(await stakeToken.balanceOf(user0))) // 299.xxx, fees
    console.log(stakeWethBalance)
    await handleRedeem(fixture, {
        unStakeAmount: precision.token(200),
        account: user0,
        receiver: user0.address,
        oracle: [{ token: wethAddr, minPrice: tokenPrice1, maxPrice: tokenPrice1 }],
    })
})
```

## Recommendation

transfer funds from the portfolio vault to the market vault during the minting process

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a denial‑of‑service condition that arises from a mismatch between where staked assets are deposited and where redemption pulls the assets. When a liquidity provider stakes tokens using the mint function with the isCollateral flag set to true, the contract routes the deposited funds to a portfolio vault instead of the LP vault that backs the stake token. Conversely, when the flag is false the funds are sent to the LP vault. The redeem function, however, always attempts to withdraw the required amount from the LP vault regardless of the origin of the underlying deposit. This design flaw breaks the accounting assumption that every minted stake token is fully backed by the balance of the LP vault. If at least one stake has been made with isCollateral = true, the portfolio vault holds a portion of the total collateral while the LP vault may not contain enough assets to satisfy subsequent redemption requests. When a user (or an attacker) then calls redeem, the contract checks the LP vault balance, finds it insufficient, and the transaction reverts. From the user’s perspective the UI may display a redemption failure, the token balance remains unchanged, or the user receives no funds despite having a positive stake token balance. The impact is that legitimate LP token holders can be prevented from withdrawing their assets, effectively locking their funds and causing a denial of service for the LP pool. The issue can be triggered in normal operation whenever a mix of collateral and non‑collateral stakes occurs, and it can be exploited deliberately: an attacker stakes with isCollateral = true to move assets away from the LP vault, then redeems from the LP vault, exhausting its balance and causing other users’ redemption attempts to fail. The problem was discovered during a security audit by reproducing a test case where one user stakes with collateral, another stakes without, and the second user’s redemption succeeds while the first user’s subsequent redemption reverts. The bug is hard to notice because the deposit and redemption paths are separate; the contract does not enforce a balance invariant across vaults, and the failure only appears at redemption time. To remediate, the protocol should ensure that all minted assets that back stake tokens are stored in the same vault used for redemption, or it should transfer the necessary amount from the portfolio vault to the LP vault during the minting process, or adjust the redemption logic to draw from both vaults, thereby restoring the accounting invariant and preventing the denial‑of‑service scenario.
