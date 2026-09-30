---
id: 4588
severity: "High"
---

# Migration will be impossible in case token has vesting recipients Submitted by deadrosesxyz, also found by Aamirusmani1552, trachev and KupiaSec

## Description

When creating a token, user can specify vesting recipients. In this case, the tokens are minted to the token contract itself, and recipients have to claim them directly. Then, only the remaining of the initial supply is minted to the Airlock:
```solidity
for (uint256 i; i < length; ++i) {
    uint256 amount = amounts_[i];
    getVestingDataOf[recipients_[i]].totalAmount += amount;
    require(
        getVestingDataOf[recipients_[i]].totalAmount <= maxPreMintPerAddress,
        MaxPreMintPerAddressExceeded(getVestingDataOf[recipients_[i]].totalAmount, maxPreMintPerAddress)
    );
    vestedTokens += amount;
}
uint256 maxTotalPreMint = initialSupply * MAX_TOTAL_PRE_MINT_WAD / 1 ether;
require(vestedTokens <= maxTotalPreMint, MaxTotalPreMintExceeded(vestedTokens, maxTotalPreMint));
if (vestedTokens > 0) {
    _mint(address(this), vestedTokens);
}
_mint(recipient, initialSupply - vestedTokens);
```
However, when migrating, the Airlock contract assumes it holds all asset tokens which are not sent initially to be sold on univ3/v4. And it attempts to send these tokens to the migrator.
```solidity
if (token0 == asset) {
    total0 += assetData.totalSupply - assetData.numTokensToSell;
    // assumes it holds all of the non-sold tokens
} else {
    total1 += assetData.totalSupply - assetData.numTokensToSell;
}
ERC20(token0).safeTransfer(address(assetData.liquidityMigrator), total0);
ERC20(token1).safeTransfer(address(assetData.liquidityMigrator), total1);
```
For this reason, if there are any vesting recipients, the following transfer would fail, due to insufficient funds. As this would brick migration, it would make the asset tokens worthless and all of the numeraire collected will be stuck.

Impact Explanation:
As migration would be stuck and all funds would be lost, High is appropriate.

## Proof of Concept

Add the following test to Airlock.t.sol:
```solidity
function test_migrateAirlock() public {
    // vm.skip(true);
    (address hook, address asset) = test_create_DeploysV4();
    PoolKey memory poolKey = PoolKey({
        currency0: Currency.wrap(address(numeraire)),
        currency1: Currency.wrap(asset),
        fee: 3000,
        tickSpacing: DEFAULT_TICK_SPACING,
        hooks: IHooks(hook)
    });
    // Deploy swapRouter
    swapRouter = new PoolSwapTest(manager);
    V4Quoter quoter = new V4Quoter(manager);
    bool isToken0 = asset < address(numeraire) ? true : false;
    CustomRouter router = new CustomRouter(swapRouter, quoter, poolKey, isToken0, false);
    // changed isUsingEth to no
    vm.warp(DEFAULT_ENDING_TIME - 1);
    uint256 amountIn = router.computeBuyExactOut(0.5e27);
    numeraire.mint(address(this), amountIn);
    numeraire.approve(address(router), amountIn);
    router.buyExactOut(0.5e27);
    vm.warp(DEFAULT_ENDING_TIME);
    vm.expectRevert("TRANSFER_FAILED");
    airlock.migrate(asset);
}
```
You'd also have to set up the test suite to provide vested tokens as follows:
```solidity
function test_create_DeploysV4() public returns (address, address) {
    address[] memory users = new address[](2);
    // @audit - comment out if airdrop is not present.
    users[0] = address(1337);
    users[1] = address(1338);
    uint256[] memory amounts = new uint256[](2);
    amounts[0] = 1e25;
    amounts[1] = 1e25;
    bytes memory tokenFactoryData =
        abi.encode(DEFAULT_TOKEN_NAME, DEFAULT_TOKEN_SYMBOL, 0, 0, users, amounts);
    // changed here to include airdrop users
    uint160 sqrtPrice = TickMath.getSqrtPriceAtTick(DEFAULT_START_TICK);
    bytes memory poolInitializerData = abi.encode(
        sqrtPrice,
        0,
        // @audit, changed from DEFAULT_MIN_PROCEEDS
        DEFAULT_MAX_PROCEEDS,
        DEFAULT_STARTING_TIME,
        DEFAULT_ENDING_TIME,
        DEFAULT_START_TICK,
        DEFAULT_END_TICK,
        DEFAULT_EPOCH_LENGTH,
        DEFAULT_GAMMA,
        false,
        DEFAULT_PD_SLUGS
    );
    (bytes32 salt, address hook, address asset) = mineV4(
        MineV4Params(
            address(airlock),
            address(manager),
            DEFAULT_INITIAL_SUPPLY,
            DEFAULT_INITIAL_SUPPLY - 2e25,
            address(numeraire), // changed from address(0)
            tokenFactory,
            tokenFactoryData,
            uniswapV4Initializer,
            poolInitializerData
        )
    );
    airlock.create(
        CreateParams(
            DEFAULT_INITIAL_SUPPLY,
            DEFAULT_INITIAL_SUPPLY - 2e25,
            // setting numTokensToSell
            address(numeraire), // changed from address(0)
            tokenFactory,
            tokenFactoryData,
            governanceFactory,
            abi.encode(DEFAULT_TOKEN_NAME),
            uniswapV4Initializer,
            poolInitializerData,
            uniswapV2LiquidityMigrator,
            new bytes(0),
            address(0xb0b),
            salt
        )
    );
    return (hook, asset);
}
```
Also, set up a numeraire asset within the test contract.
```solidity
TestERC20 numeraire;

function setUp() public {
    vm.createSelectFork(vm.envString("MAINNET_RPC_URL"), 21_093_509);
    vm.warp(DEFAULT_STARTING_TIME);
    numeraire = new TestERC20(1e18);
```

## Recommendation

Account for the vested tokens.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a logical accounting flaw in the migration routine of the Airlock contract. When a new token is created, the token factory allows the caller to specify vesting recipients. For each vesting recipient the factory mints the allocated amount to the token contract itself and records the amount in a vesting data structure, expecting the recipient to claim the tokens later. The remaining supply is minted directly to the Airlock contract. During migration the Airlock code calculates the amount of tokens it believes it holds by taking the total token supply and subtracting the number of tokens that are intended to be sold (assetData.numTokensToSell). It then attempts to transfer this calculated amount to the liquidity migrator. The calculation assumes that the Airlock contract holds the entire unsold balance, but it ignores the portion of the supply that was minted to the token contract for vesting. Consequently, if any vesting recipients exist, the actual balance of the Airlock contract is lower than the calculated amount, causing the ERC20 safeTransfer to revert with a transfer failure. This failure aborts the migration process, leaving the asset token effectively immobile: users cannot migrate, the asset appears worthless, and the numeraire collected for the migration remains locked in the contract. The issue manifests only when the token is deployed with vesting recipients; without vesting the balance matches the expectation and migration succeeds. It was discovered during a security audit that exercised the migration path with a test token containing vesting allocations, where the test observed a revert on the transfer step. The bug is subtle because the contract’s state variables (totalSupply and numTokensToSell) suggest that the full unsold amount is available, masking the fact that a subset of tokens resides in the contract’s own balance for vesting. The class of bug is an accounting mismatch or incorrect balance assumption in a token migration routine, similar to “insufficient balance due to internal minting” errors. From a user perspective, a migration transaction simply fails with a generic TRANSFER_FAILED error, the UI may show no progress, and the expected outcome – receiving migrated liquidity – never occurs, leading to confusion and potential loss of confidence. The proper fix is to adjust the migration logic to account for tokens that are minted to the token contract for vesting, either by reducing the transferred amount by the vested balance or by allowing the vesting contract to release those tokens before migration. In conceptual terms, the migration routine must query the actual token balance held by the Airlock contract rather than inferring it from total supply minus the sell amount.
