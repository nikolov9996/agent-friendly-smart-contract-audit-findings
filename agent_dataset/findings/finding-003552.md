---
id: 3552
severity: "High"
---

# Unfair Penalty Fees in Pipeline Convert

## Description

```solidity
function calculatePerWellCapacity(
    address wellToken,
    uint256 amountInDirectionOfPeg,
    uint256 cumulativePenalty,
    ConvertCapacity storage convertCap,
    uint256 pdCapacityToken
) internal view returns (uint256, uint256) {
    uint256 tokenWellCapacity = abs(LibDeltaB.cappedReservesDeltaB(wellToken)); // @audit new deltaB. i.e: 0
    pdCapacityToken = convertCap.wellConvertCapacityUsed[wellToken].add(amountInDirectionOfPeg); // @audit user contributed towards peg. value: 400
    if (pdCapacityToken > tokenWellCapacity) { // @audit 400 > 0
        cumulativePenalty = cumulativePenalty.add(pdCapacityToken.sub(tokenWellCapacity)); //@audit user got an unfair penalty fee of 400 when it should be 0. 
    }

    return (cumulativePenalty, pdCapacityToken);
}
```
The Pipeline Convert will penalize users contributing towards the peg before the conversion capacity is fully reached. This happens because:

In LibConvert, the cumulativePenalty for the Well uses the current cappedReservesDeltaB value, which is read from the well's pump.

If the timestamp of the transaction is greater than the last time the well reserves were updated when the user applies the advanced farm calls, Basin will:
Update the reserves.
Save the lastTimestamp as the current block.timestamp.

If readCappedReserves is called again in the same transaction, it will return the freshly updated reserves that the user just updated.

MultiflowPump from Basin

```solidity
function readCappedReserves(
    address well,
    bytes calldata data
) external view returns (uint256[] memory cappedReserves) {
    (, uint256 capInterval, CapReservesParameters memory crp) =
        abi.decode(data, (bytes16, uint256, CapReservesParameters));
    bytes32 slot = _getSlotForAddress(well);
    uint256[] memory currentReserves = IWell(well).getReserves();
    uint8 numberOfReserves;
    uint40 lastTimestamp;
    (numberOfReserves, lastTimestamp, cappedReserves) = slot.readLastReserves();
    if (numberOfReserves == 0) {
        revert NotInitialized();
    }
    uint256 deltaTimestamp = _getDeltaTimestamp(lastTimestamp);
    if (deltaTimestamp == 0) {
        return cappedReserves;
    }

    uint256 capExponent = calcCapExponent(deltaTimestamp, capInterval);
    cappedReserves = _capReserves(well, cappedReserves, currentReserves, capExponent, crp);
}
```
The issue occurs in the following scenario:
User calls PipelineConvertFacet -> pipelineConvert.
User applies advanced farm calls, changing the Well reserves towards the peg.
Basin updates the reserves to match the current state (when within the max cap).
When applying the penalty fee per Well, the code reads from cappedReserves again.

Example:
Previous Well deltaB: -400
User executes advanced farm calls
Current deltaB for Well capped reserves: 0

When calculating the penalty fee, the user will be charged for the value they contributed towards the peg, even though they did not surpass the conversion capacity.
Users contributing to maintaining the peg will incur a full penalty based on their contribution. For example, if the deltaB changes from -400 to 0, the user will pay a penalty of 400.
Beanstalk will discourage users from helping to maintain the peg's stability.

## Proof of Concept

Insert the code below into PipelineConvertTest.

```solidity
function testCalculateStalkPenalty_applyWrongFee() public {
    addEthToWell(users[1], 1 ether);
    addBeansToWell(users[1], 1000e6);

    addBeansToWell(users[1], 99);
    addBeansToWell(users[1], 100); // -100 deltaB

    // cappedReserves after advanced farm calls moves from -100 to 0.
    addEthToWell(users[1], 2e11);

    int256 tokenWellCapacity = LibDeltaB.cappedReservesDeltaB(beanEthWell);
    console.log("tokenWellCapacity before");
    printCappedDeltaB(tokenWellCapacity);

    updateMockPumpUsingWellReserves(beanEthWell);

    LibConvert.DeltaBStorage memory dbs;
    dbs.beforeOverallDeltaB = -100;
    dbs.afterOverallDeltaB = 0;
    dbs.beforeInputTokenDeltaB = -100;
    dbs.afterInputTokenDeltaB = 0;
    dbs.beforeOutputTokenDeltaB = 0;
    dbs.afterOutputTokenDeltaB = 0;

    uint256 bdvConverted = IERC20(beanEthWell).balanceOf(users[1]);
    uint256 overallCappedDeltaB = 100;
    address inputToken = beanEthWell;
    address outputToken = C.BEAN;

    // print deltaB
    console.log("tokenWellCapacity after ");
    tokenWellCapacity = LibDeltaB.cappedReservesDeltaB(beanEthWell);
    printCappedDeltaB(tokenWellCapacity);

    (uint256 penalty, , , ) = LibConvert.calculateStalkPenalty(
        dbs,
        bdvConverted,
        overallCappedDeltaB,
        inputToken,
        outputToken
    );

    assertEq(penalty, 0, "User1 shouldn't pay any fee");
}

function addBeansToWell(address user, uint256 amount) public returns (uint256 lpAmountOut) {
    MockToken(C.BEAN).mint(user, amount);

    vm.prank(user);
    MockToken(C.BEAN).approve(beanEthWell, amount);

    uint256[] memory tokenAmountsIn = new uint256[](2);
    tokenAmountsIn[0] = amount;
    tokenAmountsIn[1] = 0;

    vm.prank(user);
    lpAmountOut = IWell(beanEthWell).addLiquidity(tokenAmountsIn, 0, user, type(uint256).max);

    // approve spending well token to beanstalk
    vm.prank(user);
    MockToken(beanEthWell).approve(BEANSTALK, type(uint256).max);
}

function printCappedDeltaB(int256 deltaB) internal { 
    if (deltaB < 0) { 
        console.log("- cappedDeltaB: %d", LibConvert.abs(deltaB));
    } else { 
        console.log("+ cappedDeltaB: %d", LibConvert.abs(deltaB));
    }
}
```
Run: forge test --match-test testCalculateStalkPenalty_applyWrongFee -vv

Output:
```solidity
 tokenWellCapacity before
cappedDeltaB: 100
  tokenWellCapacity after 
cappedDeltaB: 0
Failing tests:
Encountered 1 failing test in test/foundry/PipelineConvert.t.sol:PipelineConvertTest
[FAIL. Reason: User1 shouldn't pay any fee: 100 != 0] testCalculateStalkPenalty_applyWrongFee() (gas: 610008)

Encountered a total of 1 failing tests, 0 tests succeeded
```

## Recommendation

```diff
function calculatePerWellCapacity(
    address wellToken,
    uint256 amountInDirectionOfPeg,
    uint256 cumulativePenalty,
    ConvertCapacity storage convertCap,
    uint256 pdCapacityToken,
    uint256 tokenWellCapacity
) internal view returns (uint256, uint256) {
    uint256 tokenWellCapacity = abs(LibDeltaB.cappedReservesDeltaB(wellToken));
    pdCapacityToken = convertCap.wellConvertCapacityUsed[wellToken].add(amountInDirectionOfPeg);
    if (pdCapacityToken > tokenWellCapacity) {
        cumulativePenalty = cumulativePenalty.add(pdCapacityToken.sub(tokenWellCapacity));
    }

    return (cumulativePenalty, pdCapacityToken);
}
```
The LibDeltaB.cappedReservesDeltaB per Well should be read before the advanced farm calls and then passed as a parameter to LibConvert.applyStalkPenalty until it reaches calculatePerWellCapacity.

## Derived Narrative

The following field is derived content and may not be source-grounded:

An unfair penalty fee is applied in the PipelineConvert function when a user contributes tokens toward the peg of a Well but the conversion capacity has not been exceeded. The root cause is that the calculation of the well’s token capacity (tokenWellCapacity) reads the capped reserves deltaB after the Basin pump has already updated the Well’s reserves within the same transaction. Because the cappedReservesDeltaB becomes zero after the update, the condition `pdCapacityToken > tokenWellCapacity` evaluates true even though the user’s contribution does not exceed the actual capacity. The contract then adds the full contribution amount to the cumulativePenalty, charging the user a fee that should be zero. This can be exploited by simply performing an advanced farm call that moves the Well’s deltaB from a negative value toward zero and then invoking pipelineConvert in the same transaction; the user will be deducted an amount equal to their contribution as a penalty. The impact is a loss of funds for honest participants who are trying to stabilize the peg, leading to unexpected balance reductions, zero refunds, or missing stalk rewards. The vulnerability manifests only when the reserve‑updating function (`readCappedReserves` via MultiflowPump) is called earlier in the transaction and the penalty calculation reads the updated capped reserves later. All users of the Beanstalk protocol who interact with the PipelineConvert facet are affected, as are the protocol’s economic incentives because the penalty discourages peg‑maintaining behavior. The issue was discovered during a security audit and reproduced with a targeted test that showed a penalty of 400 tokens when the expected penalty was zero. It is hard to notice because the code path appears correct and the penalty logic is only wrong under the specific ordering of state changes inside a single transaction. The proper fix is to capture the well’s capped deltaB before any reserve‑updating calls and pass that immutable value to the penalty calculation, ensuring the penalty is computed against the pre‑update capacity. In abstract terms, the bug is a state‑dependency timing error that leads to an incorrect accounting of conversion capacity and an unjust fee.
